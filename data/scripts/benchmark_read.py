import random
import os
import time
import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import TransientError, ServiceUnavailable

# Load credentials from .env file
load_dotenv()

# 🔑 CognoDB Cloud Credentials
URI = os.getenv("COGNODB_URI")
USER = os.getenv("COGNODB_USER")
PASSWORD = os.getenv("COGNODB_PASSWORD")

# 🎯 Benchmark Configuration
WARMUP_RUNS = 10
MEASURED_RUNS = 100


def run_workloads():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    with driver.session() as session:
        print("⚡ Starting Read Workloads Benchmark on CognoDB Cloud...")
        print(f"🔄 Configuration: {WARMUP_RUNS} Warm-up runs | {MEASURED_RUNS} Measured iterations per workload\n")

        # 📌 Workload Definitions (Optimized for Free-Tier Memory Limits)
        workloads = {
            "1. Point Lookup (Indexed Movie ID)": {
                "query": (
                    "MATCH (m:Movie {id: $id}) "
                    "RETURN m.title AS title, m.genres AS genres"
                ),
                "param_gen": lambda: {"id": str(random.randint(1, 1000))}
            },
            "2. 1-Hop Traversal (User -> Rated Movies)": {
                "query": (
                    "MATCH (u:User {id: $id})-[r:RATED]->(m:Movie) "
                    "RETURN m.title, r.rating"
                ),
                "param_gen": lambda: {"id": str(random.randint(1, 600))}
            },
            "3. 2-Hop Traversal (User -> Movie -> Users)": {
                "query": (
                    "MATCH (u:User {id: $id})-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User) "
                    "RETURN count(DISTINCT u2) AS co_watchers"
                ),
                "param_gen": lambda: {"id": str(random.randint(1, 600))}
            },
            "4. 3-Hop Traversal (User -> Movie -> User -> Rec Movies)": {
                "query": (
                    "MATCH (u:User {id: $id})-[r1:RATED]->(m:Movie) WITH m LIMIT 10 "
                    "MATCH (m)<-[r2:RATED]-(u2:User) WITH u2 LIMIT 20 "
                    "MATCH (u2)-[r3:RATED]->(m2:Movie) "
                    "RETURN m2.title AS recommended, count(m2) AS score "
                    "ORDER BY score DESC LIMIT 10"
                ),
                "param_gen": lambda: {"id": str(random.randint(1, 600))}
            },
            "5. Aggregation (Avg Rating per Genre)": {
                "query": (
                    "MATCH (u:User)-[r:RATED]->(m:Movie) "
                    "RETURN m.genres AS genre, avg(r.rating) AS avg_rating, count(r) AS total_ratings "
                    "ORDER BY total_ratings DESC LIMIT 10"
                ),
                "param_gen": lambda: {}
            }
        }

        results = []

        for name, config in workloads.items():
            print(f"🏃 Running: {name}...")
            query = config["query"]
            param_gen = config["param_gen"]

            # 🔥 1. Warm-up Phase
            try:
                for _ in range(WARMUP_RUNS):
                    params = param_gen()
                    session.run(query, params).consume()
            except Exception as e:
                print(f"⚠️ Warm-up notice for {name}: {e}")

            # ⏱️ 2. Measured Runs
            latencies_ms = []
            timed_out = False

            for _ in range(MEASURED_RUNS):
                params = param_gen()
                try:
                    start = time.perf_counter()
                    session.run(query, params).consume()
                    end = time.perf_counter()
                    latencies_ms.append((end - start) * 1000.0)
                except TransientError:
                    timed_out = True
                    break
                except Exception as e:
                    print(f"⚠️ Error during run: {e}")
                    timed_out = True
                    break

            if timed_out or not latencies_ms:
                results.append({
                    "Workload": name,
                    "p50 (ms)": "Timeout",
                    "p95 (ms)": "Timeout",
                    "Avg (ms)": "Timeout"
                })
            else:
                p50 = np.percentile(latencies_ms, 50)
                p95 = np.percentile(latencies_ms, 95)
                avg = np.mean(latencies_ms)
                results.append({
                    "Workload": name,
                    "p50 (ms)": f"{p50:.2f}",
                    "p95 (ms)": f"{p95:.2f}",
                    "Avg (ms)": f"{avg:.2f}"
                })

        # 📈 Display Results Matrix
        print("\n" + "=" * 80)
        print("📊 COGNODB CLOUD QUERY LATENCY BENCHMARK RESULTS")
        print("=" * 80)
        print(f"{'Workload Name':<45} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'Avg (ms)':<10}")
        print("-" * 80)
        for res in results:
            print(f"{res['Workload']:<45} | {res['p50 (ms)']:<10} | {res['p95 (ms)']:<10} | {res['Avg (ms)']:<10}")
        print("=" * 80)

    driver.close()

if __name__ == "__main__":
    run_workloads()
