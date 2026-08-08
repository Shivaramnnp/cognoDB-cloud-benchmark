import os
import random
import time
import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase, exceptions

# Load credentials from .env file
load_dotenv()

# 🔑 Credentials Configuration
# Switch URI / USER / PASSWORD between Neo4j Aura and Memgraph
URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DB_NAME = os.getenv("DB_TARGET", "Neo4j AuraDB")

WARMUP_RUNS = 10
MEASURED_RUNS = 100


def run_benchmark():
  driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

  with driver.session() as session:
    print(f"⚡ Starting Read Workloads on {DB_NAME}...")

    workloads = {
        "1. Point Lookup": (
            "MATCH (m:Movie {id: $id}) RETURN m.title, m.genres",
            lambda: {"id": str(random.randint(1, 1000))},
        ),
        "2. 1-Hop Traversal": (
            "MATCH (u:User {id: $id})-[r:RATED]->(m:Movie) RETURN m.title,"
            " r.rating",
            lambda: {"id": str(random.randint(1, 600))},
        ),
        "3. 2-Hop Traversal": (
            (
                "MATCH (u:User {id: $id})-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User)"
                " RETURN count(DISTINCT u2)"
            ),
            lambda: {"id": str(random.randint(1, 600))},
        ),
        "4. 3-Hop Traversal": (
            (
                "MATCH (u:User {id: $id})-[r1:RATED]->(m:Movie) WITH m LIMIT 10"
                " MATCH (m)<-[r2:RATED]-(u2:User) WITH u2 LIMIT 20 MATCH"
                " (u2)-[r3:RATED]->(m2:Movie) RETURN m2.title, count(m2) AS s"
                " ORDER BY s DESC LIMIT 10"
            ),
            lambda: {"id": str(random.randint(1, 600))},
        ),
        "5. Aggregation": (
            (
                "MATCH (u:User)-[r:RATED]->(m:Movie) RETURN m.genres,"
                " avg(r.rating), count(r) AS c ORDER BY c DESC LIMIT 10"
            ),
            lambda: {},
        ),
    }

    results = []
    for name, (query, param_gen) in workloads.items():
      print(f"🏃 {name}...")

      # Warmup
      for _ in range(WARMUP_RUNS):
        try:
          session.run(query, param_gen()).consume()
        except Exception:
          pass

      # Measured
      latencies = []
      for _ in range(MEASURED_RUNS):
        start = time.perf_counter()
        try:
          session.run(query, param_gen()).consume()
          end = time.perf_counter()
          latencies.append((end - start) * 1000.0)
        except Exception:
          pass

      if latencies:
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        avg = np.mean(latencies)
        results.append((name, f"{p50:.2f}", f"{p95:.2f}", f"{avg:.2f}"))
      else:
        results.append((name, "Timeout", "Timeout", "Timeout"))

    print(f"\n--- 📊 {DB_NAME} Latency Results ---")
    for r in results:
      print(f"{r[0]:<25} | p50: {r[1]} ms | p95: {r[2]} ms | Avg: {r[3]} ms")

  driver.close()


if __name__ == "__main__":
  run_benchmark()
