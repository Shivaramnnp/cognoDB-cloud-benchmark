import concurrent.futures
import os
import random
import time
from dotenv import load_dotenv
from falkordb import FalkorDB
import kuzu
from neo4j import GraphDatabase
import numpy as np

# Load environment variables from .env file
load_dotenv()

# ==========================================
# 🔑 Credentials — loaded from .env file
# ==========================================
# 1. CognoDB Cloud
COGNODB_URI = os.getenv("COGNODB_URI")
COGNODB_USER = os.getenv("COGNODB_USER")
COGNODB_PASS = os.getenv("COGNODB_PASSWORD")

# 2. FalkorDB Cloud
FALKOR_HOST = os.getenv("FALKORDB_HOST")
FALKOR_PORT = int(os.getenv("FALKORDB_PORT", "50107"))
FALKOR_USER = os.getenv("FALKORDB_USER")
FALKOR_PASS = os.getenv("FALKORDB_PASSWORD")

# 3. Memgraph Cloud
MEMGRAPH_URI = os.getenv("MEMGRAPH_URI")
MEMGRAPH_USER = os.getenv("MEMGRAPH_USER")
MEMGRAPH_PASS = os.getenv("MEMGRAPH_PASSWORD")

# 4. Neo4j AuraDB
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD")

# 5. Kùzu DB (Embedded)
KUZU_DB_PATH = "./kuzu_db"

WARMUP = 5
MEASURED = 50


# ==========================================
# 🔍 Query Definitions
# ==========================================
def get_queries(db_type="bolt"):
  is_int_id = db_type == "kuzu"
  id_gen = (
      lambda: random.randint(1, 600)
      if is_int_id
      else str(random.randint(1, 600))
  )
  movie_id_gen = (
      lambda: random.randint(1, 1000)
      if is_int_id
      else str(random.randint(1, 1000))
  )

  return {
      "1. Point Lookup": (
          "MATCH (m:Movie {id: $id}) RETURN m.title, m.genres",
          lambda: {"id": movie_id_gen()},
      ),
      "2. 1-Hop Traversal": (
          "MATCH (u:User {id: $id})-[r:RATED]->(m:Movie) RETURN m.title,"
          " r.rating",
          lambda: {"id": id_gen()},
      ),
      "3. 2-Hop Traversal": (
          "MATCH (u:User {id: $id})-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User)"
          " RETURN count(DISTINCT u2)",
          lambda: {"id": id_gen()},
      ),
      "4. 3-Hop Traversal": (
          "MATCH (u:User {id: $id})-[r1:RATED]->(m:Movie) WITH m LIMIT 10 "
          "MATCH (m)<-[r2:RATED]-(u2:User) WITH u2 LIMIT 20 "
          "MATCH (u2)-[r3:RATED]->(m2:Movie) RETURN m2.title, count(m2) AS s "
          "ORDER BY s DESC LIMIT 10",
          lambda: {"id": id_gen()},
      ),
      "5. Aggregation": (
          "MATCH (u:User)-[r:RATED]->(m:Movie) RETURN m.genres, avg(r.rating),"
          " count(r) AS c ORDER BY c DESC LIMIT 10",
          lambda: {},
      ),
  }


# ==========================================
# 🏃 Runner Functions
# ==========================================
def run_bolt_db(name, uri, user, password):
  print(f"🏃 Benchmarking {name}...")
  results = {}
  try:
    auth = (user, password) if user else None
    driver = GraphDatabase.driver(uri, auth=auth)
    driver.verify_connectivity()
    queries = get_queries("bolt")

    with driver.session() as session:
      for q_name, (query, param_gen) in queries.items():
        for _ in range(WARMUP):
          try:
            session.run(query, param_gen()).consume()
          except Exception:
            pass

        latencies = []
        for _ in range(MEASURED):
          start = time.perf_counter()
          try:
            session.run(query, param_gen()).consume()
            end = time.perf_counter()
            latencies.append((end - start) * 1000.0)
          except Exception:
            pass

        if latencies:
          results[q_name] = (
              f"{np.percentile(latencies, 50):.2f} /"
              f" {np.percentile(latencies, 95):.2f}"
          )
        else:
          results[q_name] = "N/A"
    driver.close()
  except Exception as e:
    print(f"  ⚠️ Skipping {name} (Unreachable): {e}")
    for q_name in get_queries().keys():
      results[q_name] = "N/A"
  return results


def run_falkordb():
  print("🏃 Benchmarking FalkorDB Cloud...")
  results = {}
  try:
    db = FalkorDB(
        host=FALKOR_HOST,
        port=FALKOR_PORT,
        username=FALKOR_USER,
        password=FALKOR_PASS,
        ssl=False,
    )
    graph = db.select_graph("MovieLens")
    queries = get_queries("falkor")

    for q_name, (query, param_gen) in queries.items():
      for _ in range(WARMUP):
        try:
          graph.query(query, param_gen())
        except Exception:
          pass

      latencies = []
      for _ in range(MEASURED):
        start = time.perf_counter()
        try:
          graph.query(query, param_gen())
          end = time.perf_counter()
          latencies.append((end - start) * 1000.0)
        except Exception:
          pass

      if latencies:
        results[q_name] = (
            f"{np.percentile(latencies, 50):.2f} /"
            f" {np.percentile(latencies, 95):.2f}"
        )
      else:
        results[q_name] = "N/A"
  except Exception as e:
    print(f"  ⚠️ Skipping FalkorDB: {e}")
    for q_name in get_queries().keys():
      results[q_name] = "N/A"
  return results


def run_kuzu():
  print("🏃 Benchmarking Kùzu DB (Embedded)...")
  results = {}
  try:
    db = kuzu.Database(KUZU_DB_PATH)
    conn = kuzu.Connection(db)
    queries = get_queries("kuzu")

    for q_name, (query, param_gen) in queries.items():
      for _ in range(WARMUP):
        conn.execute(query, param_gen())

      latencies = []
      for _ in range(MEASURED):
        start = time.perf_counter()
        conn.execute(query, param_gen())
        end = time.perf_counter()
        latencies.append((end - start) * 1000.0)

      results[q_name] = (
          f"{np.percentile(latencies, 50):.2f} /"
          f" {np.percentile(latencies, 95):.2f}"
      )
  except Exception as e:
    print(f"  ⚠️ Skipping Kùzu DB: {e}")
    for q_name in get_queries().keys():
      results[q_name] = "N/A"
  return results


def run_concurrency_sweep():
  print("\n🔥 Running CognoDB Cloud Concurrency Sweep (80/20 Read/Write)...")
  driver = GraphDatabase.driver(COGNODB_URI, auth=(COGNODB_USER, COGNODB_PASS))

  def worker_task(stop_time):
    cnt = 0
    with driver.session() as session:
      while time.time() < stop_time:
        if random.random() < 0.8:
          session.run(
              "MATCH (u:User {id: $id})-[r:RATED]->(m:Movie) RETURN m.title",
              id=str(random.randint(1, 600)),
          ).consume()
        else:
          session.run(
              "MERGE (u:User {id: $uid}) MERGE (m:Movie {id: $mid}) CREATE"
              " (u)-[:RATED {rating: $rating}]->(m)",
              uid=f"bench_{random.randint(8000, 9999)}",
              mid=str(random.randint(1, 1000)),
              rating=4.0,
          ).consume()
        cnt += 1
    return cnt

  sweep_results = []
  for threads in [1, 10, 40]:
    stop_time = time.time() + 5
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=threads
    ) as executor:
      futures = [executor.submit(worker_task, stop_time) for _ in range(threads)]
      total = sum(f.result() for f in futures)
    qps = total / 5.0
    sweep_results.append((threads, total, qps))

  driver.close()
  return sweep_results


# ==========================================
# 📊 Execution & Main Summary Table
# ==========================================
if __name__ == "__main__":
  print("=" * 115)
  print("⚡ STARTING MASTER GRAPH DATABASE BENCHMARK SUITE (ALL 5 DATABASES)")
  print("=" * 115 + "\n")

  cogno_res = run_bolt_db(
      "CognoDB Cloud", COGNODB_URI, COGNODB_USER, COGNODB_PASS
  )
  falkor_res = run_falkordb()
  kuzu_res = run_kuzu()
  memgraph_res = run_bolt_db(
      "Memgraph Cloud", MEMGRAPH_URI, MEMGRAPH_USER, MEMGRAPH_PASS
  )
  neo4j_res = run_bolt_db("Neo4j AuraDB", NEO4J_URI, NEO4J_USER, NEO4J_PASS)

  conc_res = run_concurrency_sweep()

  print("\n" + "=" * 115)
  print("📊 MASTER QUERY LATENCY COMPARISON MATRIX (p50 / p95 in ms)")
  print("=" * 115)
  print(
      f"{'Workload Name':<22} | {'CognoDB Cloud':<17} | {'FalkorDB Cloud':<17}"
      f" | {'Kùzu DB (Local)':<17} | {'Memgraph Cloud':<17} | {'Neo4j Aura':<12}"
  )
  print("-" * 115)

  for q_name in get_queries().keys():
    c_val = cogno_res.get(q_name, "N/A")
    f_val = falkor_res.get(q_name, "N/A")
    k_val = kuzu_res.get(q_name, "N/A")
    m_val = memgraph_res.get(q_name, "N/A")
    n_val = neo4j_res.get(q_name, "N/A")
    print(
        f"{q_name:<22} | {c_val:<17} | {f_val:<17} | {k_val:<17} |"
        f" {m_val:<17} | {n_val:<12}"
    )

  print("=" * 115)

  print("\n" + "=" * 60)
  print("⚡ COGNODB CLOUD CONCURRENCY SWEEP RESULTS")
  print("=" * 60)
  print(
      f"{'Threads (Clients)':<20} | {'Total Queries':<18} |"
      f" {'Throughput (QPS)':<15}"
  )
  print("-" * 60)
  for t, tot, qps in conc_res:
    print(f"{t:<20} | {tot:<18} | {qps:.2f} QPS")
  print("=" * 60)
