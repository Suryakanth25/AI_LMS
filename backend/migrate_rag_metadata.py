import sqlite3
import os

DB_PATH = "council.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if unit_id already exists
        cursor.execute("PRAGMA table_info(study_materials)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "unit_id" not in columns:
            print("Adding unit_id column to study_materials...")
            cursor.execute("ALTER TABLE study_materials ADD COLUMN unit_id INTEGER REFERENCES units(id)")
            conn.commit()
            print("Successfully added unit_id column.")
        else:
            print("unit_id column already exists.")

    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
