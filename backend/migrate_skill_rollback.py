"""
Migration: Add rollback columns to skills table
Run: python migrate_skill_rollback.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "council.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check which columns already exist
    cursor.execute("PRAGMA table_info(skills)")
    existing = {row[1] for row in cursor.fetchall()}
    
    new_columns = [
        ("is_active", "INTEGER DEFAULT 1"),
        ("auto_deactivated", "INTEGER DEFAULT 0"),
        ("deactivation_reason", "TEXT DEFAULT NULL"),
        ("previous_trained_score", "REAL DEFAULT 0.0"),
    ]
    
    for col_name, col_def in new_columns:
        if col_name not in existing:
            try:
                sql = f"ALTER TABLE skills ADD COLUMN {col_name} {col_def}"
                print(f"  Adding column: {col_name}")
                cursor.execute(sql)
            except Exception as e:
                print(f"  Error adding {col_name}: {e}")
        else:
            print(f"  Column already exists: {col_name}")
    
    conn.commit()
    conn.close()
    print("✅ Migration complete!")


if __name__ == "__main__":
    migrate()
