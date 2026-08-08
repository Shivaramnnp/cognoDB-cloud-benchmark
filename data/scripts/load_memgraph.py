import csv
import os
import time
from neo4j import GraphDatabase

# 🔑 Memgraph Credentials & Dataset Path
URI = "bolt+ssc://3.69.173.236:7687"
USER = "shivaramnnp@gmail.com"
PASSWORD = "@Shiva9701"
DATA_DIR = "/Users/shivarampatel/Desktop/ml-latest-small"


def load_data():
  driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
  start_time = time.time()
  nodes_created = 0
  rels_created = 0

  with driver.session() as session:
    # 🎬 1. Load Movies
    print("🎬 Loading Movies into Memgraph...")
    movies_file = os.path.join(DATA_DIR, "movies.csv")
    with open(movies_file, "r", encoding="utf-8") as f:
      reader = csv.DictReader(f)
      movies_batch = []
      for row in reader:
        movies_batch.append(
            {"id": row["movieId"], "title": row["title"], "genres": row["genres"]}
        )
        if len(movies_batch) >= 1000:
          session.run(
              "UNWIND $batch AS row MERGE (m:Movie {id: row.id}) SET m.title ="
              " row.title, m.genres = row.genres",
              batch=movies_batch,
          )
          nodes_created += len(movies_batch)
          movies_batch = []
      if movies_batch:
        session.run(
            "UNWIND $batch AS row MERGE (m:Movie {id: row.id}) SET m.title ="
            " row.title, m.genres = row.genres",
            batch=movies_batch,
        )
        nodes_created += len(movies_batch)

    # 👥 2. Load Users & Relationships
    print("👥 Loading Users & Relationships into Memgraph...")
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
          rels_created += len(ratings_batch)
          ratings_batch = []
      if ratings_batch:
        session.run(
            "UNWIND $batch AS row MERGE (u:User {id: row.userId}) WITH u, row"
            " MATCH (m:Movie {id: row.movieId}) CREATE (u)-[r:RATED {rating:"
            " row.rating}]->(m)",
            batch=ratings_batch,
        )
        rels_created += len(ratings_batch)

  elapsed_seconds = time.time() - start_time

  # 📊 Print Ingestion Metrics
  print("\n--- 📈 Memgraph Ingestion Metrics ---")
  print(f"⏱️ Total Wall-Clock Load Time: {elapsed_seconds:.2f} seconds")
  print(f"📦 Nodes/sec: {nodes_created / elapsed_seconds:.2f}")
  print(f"🔗 Relationships/sec: {rels_created / elapsed_seconds:.2f}")

  driver.close()


if __name__ == "__main__":
  load_data()
