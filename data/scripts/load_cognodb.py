import csv
import os
import time
from neo4j import GraphDatabase

# 🔑 Database Credentials & Dataset Path
URI = "bolt+s://db-3960f658.databases.cognodb.com"
USER = "cognodb"
PASSWORD = "d853adbe9fbc7a26ba884e8bbada9b37"
DATA_DIR = "/Users/shivarampatel/Desktop/ml-latest-small"


def load_data():
  # Connect using the official Neo4j driver
  driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

  with driver.session() as session:
    # 🧹 Step 0: Clear existing data for a clean benchmark run
    print("🧹 Resetting CognoDB graph data...")
    session.run("MATCH (n) DETACH DELETE n")

    start_time = time.time()

    # 🎬 Step 1: Load Movie Nodes
    print("🎬 Loading Movies into CognoDB Cloud...")
    movies_file = os.path.join(DATA_DIR, "movies.csv")
    with open(movies_file, "r", encoding="utf-8") as f:
      reader = csv.DictReader(f)
      movies_batch = []
      for row in reader:
        movies_batch.append({
            "id": row["movieId"],
            "title": row["title"],
            "genres": row["genres"],
        })
        if len(movies_batch) >= 1000:
          session.run(
              "UNWIND $batch AS row MERGE (m:Movie {id: row.id}) SET m.title ="
              " row.title, m.genres = row.genres",
              batch=movies_batch,
          )
          movies_batch = []
      if movies_batch:
        session.run(
            "UNWIND $batch AS row MERGE (m:Movie {id: row.id}) SET m.title ="
            " row.title, m.genres = row.genres",
            batch=movies_batch,
        )

    # ⚡ Step 2: Create Index on Movie ID to speed up relationship matching
    print("⚡ Creating index on Movie(id)...")
    try:
      session.run("CREATE INDEX movie_id_idx IF NOT EXISTS FOR (m:Movie) ON (m.id)")
    except Exception:
      pass  # Fallback for older Cypher syntax if needed

    # 👥 Step 3: Load User Nodes & RATED Relationships
    print("👥 Loading Users & Relationships into CognoDB Cloud...")
    ratings_file = os.path.join(DATA_DIR, "ratings.csv")
    with open(ratings_file, "r", encoding="utf-8") as f:
      reader = csv.DictReader(f)
      ratings_batch = []
      for row in reader:
        ratings_batch.append({
            "userId": row["userId"],
            "movieId": row["movieId"],
            "rating": float(row["rating"]),
        })
        if len(ratings_batch) >= 1000:
          session.run(
              "UNWIND $batch AS row MERGE (u:User {id: row.userId}) WITH u, row"
              " MATCH (m:Movie {id: row.movieId}) CREATE (u)-[r:RATED {rating:"
              " row.rating}]->(m)",
              batch=ratings_batch,
          )
          ratings_batch = []
      if ratings_batch:
        session.run(
            "UNWIND $batch AS row MERGE (u:User {id: row.userId}) WITH u, row"
            " MATCH (m:Movie {id: row.movieId}) CREATE (u)-[r:RATED {rating:"
            " row.rating}]->(m)",
            batch=ratings_batch,
        )

    elapsed_seconds = time.time() - start_time

    # 📊 Query Exact Database Counts
    nodes_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    rels_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()[
        "c"
    ]

    # 📈 Print Required Ingestion Metrics
    print("\n--- 📈 CognoDB Cloud Ingestion Metrics ---")
    print(f"⏱️ Total Wall-Clock Load Time: {elapsed_seconds:.2f} seconds")
    print(f"📦 Nodes/sec: {nodes_count / elapsed_seconds:.2f}")
    print(f"🔗 Relationships/sec: {rels_count / elapsed_seconds:.2f}")

  driver.close()


if __name__ == "__main__":
  load_data()
