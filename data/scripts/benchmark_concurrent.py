import concurrent.futures
import os
import random
import time
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load credentials from .env file
load_dotenv()

URI = os.getenv("COGNODB_URI")
USER = os.getenv("COGNODB_USER")
PASSWORD = os.getenv("COGNODB_PASSWORD")

CONCURRENCY_LEVELS = [1, 10, 40]
DURATION_SECONDS = 10


def worker_task(driver, stop_time):
  queries_count = 0
  with driver.session() as session:
    while time.time() < stop_time:
      is_read = random.random() < 0.8
      if is_read:
        # 80% Read: 1-Hop Lookup
        uid = str(random.randint(1, 600))
        session.run(
            "MATCH (u:User {id: $id})-[r:RATED]->(m:Movie) RETURN m.title",
            id=uid,
        ).consume()
      else:
        # 20% Write: Insert dynamic rating
        uid = f"benchmark_u_{random.randint(9000, 9999)}"
        mid = str(random.randint(1, 1000))
        rating = round(random.uniform(1.0, 5.0), 1)
        session.run(
            "MERGE (u:User {id: $uid}) MERGE (m:Movie {id: $mid}) CREATE"
            " (u)-[:RATED {rating: $rating}]->(m)",
            uid=uid,
            mid=mid,
            rating=rating,
        ).consume()
      queries_count += 1
  return queries_count


def run_concurrency_sweep():
  driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
  print("🔥 Starting Concurrency Sweep Benchmark (80% Read / 20% Write)...")

  for threads in CONCURRENCY_LEVELS:
    stop_time = time.time() + DURATION_SECONDS
    total_queries = 0

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=threads
    ) as executor:
      futures = [
          executor.submit(worker_task, driver, stop_time) for _ in range(threads)
      ]
      for f in concurrent.futures.as_completed(futures):
        total_queries += f.result()

    qps = total_queries / DURATION_SECONDS
    print(
        f"👥 Concurrency: {threads:2d} clients | Total Queries:"
        f" {total_queries:5d} | Sustained QPS: {qps:.2f} queries/sec"
    )

  driver.close()


if __name__ == "__main__":
  run_concurrency_sweep()
