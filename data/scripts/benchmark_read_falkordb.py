import os
import random
import time
import numpy as np
from dotenv import load_dotenv
from falkordb import FalkorDB

# Load credentials from .env file
load_dotenv()

HOST = os.getenv("FALKORDB_HOST")
PORT = int(os.getenv("FALKORDB_PORT", "50107"))
USERNAME = os.getenv("FALKORDB_USER")
PASSWORD = os.getenv("FALKORDB_PASSWORD")

WARMUP_RUNS = 10
MEASURED_RUNS = 100


def run_benchmark():
  db = FalkorDB(
      host=HOST, port=PORT, username=USERNAME, password=PASSWORD, ssl=False
  )
  graph = db.select_graph("MovieLens")

  print("⚡ Starting Read Workloads on FalkorDB Cloud...")

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

  for name, (query, param_gen) in workloads.items():
    # Warmup
    for _ in range(WARMUP_RUNS):
      try:
        graph.query(query, param_gen())
      except Exception:
        pass

    # Measured
    latencies = []
    for _ in range(MEASURED_RUNS):
      start = time.perf_counter()
      try:
        graph.query(query, param_gen())
        end = time.perf_counter()
        latencies.append((end - start) * 1000.0)
      except Exception:
        pass

    p50 = np.percentile(latencies, 50) if latencies else 0
    p95 = np.percentile(latencies, 95) if latencies else 0
    avg = np.mean(latencies) if latencies else 0
    print(
        f"{name:<25} | p50: {p50:.2f} ms | p95: {p95:.2f} ms | Avg: {avg:.2f} ms"
    )


if __name__ == "__main__":
  run_benchmark()
