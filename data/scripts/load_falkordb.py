import csv
import os
import time
from dotenv import load_dotenv
from falkordb import FalkorDB

# Load credentials from .env file
load_dotenv()

# 🔑 FalkorDB Credentials & Dataset Path
HOST = os.getenv("FALKORDB_HOST")
PORT = int(os.getenv("FALKORDB_PORT", "50107"))
USERNAME = os.getenv("FALKORDB_USER")
PASSWORD = os.getenv("FALKORDB_PASSWORD")
DATA_DIR = os.getenv("DATA_DIR", "/Users/shivarampatel/Desktop/ml-latest-small")


def load_data():
  # 🔌 Connect to FalkorDB Cloud (ssl=False)
  db = FalkorDB(
      host=HOST, port=PORT, username=USERNAME, password=PASSWORD, ssl=False
  )

  graph = db.select_graph("MovieLens")

  # 🧹 Step 0: Clear previous data to start fresh
  print("🧹 Resetting graph data...")
  try:
    graph.delete()
  except Exception:
    pass  # Ignore if graph doesn't exist yet

  # Re-select clean graph
  graph = db.select_graph("MovieLens")

  start_time = time.time()
  nodes_created = 0
  rels_created = 0

  # 🎬 Step 1: Load Movies
  print("🎬 Loading Movies into FalkorDB...")
  movies_file = os.path.join(DATA_DIR, "movies.csv")
  with open(movies_file, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    movies_batch = []
    for row in reader:
      movies_batch.append(
          {"id": row["movieId"], "title": row["title"], "genres": row["genres"]}
      )
      if len(movies_batch) >= 1000:
        graph.query(
            "UNWIND $batch AS row MERGE (m:Movie {id: row.id}) SET m.title ="
            " row.title, m.genres = row.genres",
            {"batch": movies_batch},
        )
        nodes_created += len(movies_batch)
        movies_batch = []
    if movies_batch:
      graph.query(
          "UNWIND $batch AS row MERGE (m:Movie {id: row.id}) SET m.title ="
          " row.title, m.genres = row.genres",
          {"batch": movies_batch},
      )
      nodes_created += len(movies_batch)

  # ⚡ Step 2: Create Index on Movie ID to prevent timeouts
  print("⚡ Creating index on Movie(id)...")
  graph.query("CREATE INDEX FOR (m:Movie) ON (m.id)")

  # 👥 Step 3: Load Users & Relationships
  print("👥 Loading Users & Relationships into FalkorDB...")
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
        graph.query(
            "UNWIND $batch AS row MERGE (u:User {id: row.userId}) WITH u, row"
            " MATCH (m:Movie {id: row.movieId}) CREATE (u)-[r:RATED {rating:"
            " row.rating}]->(m)",
            {"batch": ratings_batch},
        )
        rels_created += len(ratings_batch)
        ratings_batch = []
    if ratings_batch:
      graph.query(
          "UNWIND $batch AS row MERGE (u:User {id: row.userId}) WITH u, row"
          " MATCH (m:Movie {id: row.movieId}) CREATE (u)-[r:RATED {rating:"
          " row.rating}]->(m)",
          {"batch": ratings_batch},
      )
      rels_created += len(ratings_batch)

  elapsed_seconds = time.time() - start_time

  # 📊 Print Ingestion Metrics
  print("\n--- 📈 FalkorDB Ingestion Metrics ---")
  print(f"⏱️ Total Wall-Clock Load Time: {elapsed_seconds:.2f} seconds")
  print(f"📦 Nodes/sec: {nodes_created / elapsed_seconds:.2f}")
  print(f"🔗 Relationships/sec: {rels_created / elapsed_seconds:.2f}")


if __name__ == "__main__":
  load_data()
