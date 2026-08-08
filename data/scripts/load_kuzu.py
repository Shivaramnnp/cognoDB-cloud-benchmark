import csv
import os
import shutil
import time
import kuzu

DATA_DIR = "/Users/shivarampatel/Desktop/ml-latest-small"
DB_PATH = "./kuzu_db"


def load_data():
  # 🧹 Step 0: Clear previous Kùzu database folder if it exists
  print("🧹 Resetting local Kùzu database...")
  if os.path.exists(DB_PATH):
    shutil.rmtree(DB_PATH)

  # 🔌 Initialize Kùzu DB
  db = kuzu.Database(DB_PATH)
  conn = kuzu.Connection(db)

  # 🛠️ Define Schema (Kùzu requires schema declaration for primary keys and tables)
  conn.execute(
      "CREATE NODE TABLE Movie(id INT64, title STRING, genres STRING, PRIMARY"
      " KEY(id));"
  )
  conn.execute("CREATE NODE TABLE User(id INT64, PRIMARY KEY(id));")
  conn.execute("CREATE REL TABLE RATED(FROM User TO Movie, rating DOUBLE);")

  start_time = time.time()
  nodes_created = 0
  rels_created = 0

  # 🎬 Step 1: Load Movies
  print("🎬 Loading Movies into Kùzu DB...")
  movies_file = os.path.join(DATA_DIR, "movies.csv")
  with open(movies_file, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    movies_batch = []
    for row in reader:
      movies_batch.append({
          "id": int(row["movieId"]),
          "title": row["title"],
          "genres": row["genres"],
      })
      if len(movies_batch) >= 1000:
        for item in movies_batch:
          conn.execute(
              "CREATE (m:Movie {id: $id, title: $title, genres: $genres})", item
          )
        nodes_created += len(movies_batch)
        movies_batch = []
    if movies_batch:
      for item in movies_batch:
        conn.execute(
            "CREATE (m:Movie {id: $id, title: $title, genres: $genres})", item
        )
      nodes_created += len(movies_batch)

  # 👥 Step 2: Load Users & Relationships
  print("👥 Loading Users & Relationships into Kùzu DB...")
  ratings_file = os.path.join(DATA_DIR, "ratings.csv")

  created_users = set()

  with open(ratings_file, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    ratings_batch = []
    for row in reader:
      user_id = int(row["userId"])
      if user_id not in created_users:
        conn.execute("CREATE (u:User {id: $id})", {"id": user_id})
        created_users.add(user_id)
        nodes_created += 1

      ratings_batch.append({
          "userId": user_id,
          "movieId": int(row["movieId"]),
          "rating": float(row["rating"]),
      })

      if len(ratings_batch) >= 1000:
        for item in ratings_batch:
          conn.execute(
              "MATCH (u:User {id: $userId}), (m:Movie {id: $movieId}) CREATE"
              " (u)-[r:RATED {rating: $rating}]->(m)",
              item,
          )
        rels_created += len(ratings_batch)
        ratings_batch = []

    if ratings_batch:
      for item in ratings_batch:
        conn.execute(
            "MATCH (u:User {id: $userId}), (m:Movie {id: $movieId}) CREATE"
            " (u)-[r:RATED {rating: $rating}]->(m)",
            item,
        )
      rels_created += len(ratings_batch)

  elapsed_seconds = time.time() - start_time

  # 📊 Print Ingestion Metrics
  print("\n--- 📈 Kùzu DB Ingestion Metrics ---")
  print(f"⏱️ Total Wall-Clock Load Time: {elapsed_seconds:.2f} seconds")
  print(f"📦 Nodes/sec: {nodes_created / elapsed_seconds:.2f}")
  print(f"🔗 Relationships/sec: {rels_created / elapsed_seconds:.2f}")


if __name__ == "__main__":
  load_data()
