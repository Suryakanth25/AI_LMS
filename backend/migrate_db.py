import sqlite3
from database import SQLALCHEMY_DATABASE_URL

# Path to db file (remove sqlite:/// prefix)
db_path = "./council.db"

def run_migration():
    print(f"Migrating database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Add syllabus_data to topics
    try:
        cursor.execute("ALTER TABLE topics ADD COLUMN syllabus_data JSON DEFAULT '{}'")
        print("Added syllabus_data to topics")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("syllabus_data already exists in topics")
        else:
            print(f"Error adding syllabus_data: {e}")

    # 2. Add topic_id to study_materials
    try:
        cursor.execute("ALTER TABLE study_materials ADD COLUMN topic_id INTEGER REFERENCES topics(id)")
        print("Added topic_id to study_materials")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("topic_id already exists in study_materials")
        else:
            print(f"Error adding topic_id: {e}")

    # 3. Create sample_questions table
    # We can use sqlalchemy to create this if we want, but raw SQL is fine for prototype
    create_sq_table = """
    CREATE TABLE IF NOT EXISTS sample_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        question_type VARCHAR(50),
        difficulty VARCHAR(50),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(topic_id) REFERENCES topics(id)
    );
    """
    cursor.execute(create_sq_table)
    print("Ensured sample_questions table exists")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
