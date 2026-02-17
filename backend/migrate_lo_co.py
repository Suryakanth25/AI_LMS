import sqlite3

def migrate():
    conn = sqlite3.connect("obe_lms.db")
    cursor = conn.cursor()

    # Create Learning Outcomes Table
    create_lo_table = """
    CREATE TABLE IF NOT EXISTS learning_outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text VARCHAR(500) NOT NULL,
        code VARCHAR(50),
        unit_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(unit_id) REFERENCES units(id)
    );
    """
    cursor.execute(create_lo_table)
    print("Created learning_outcomes table.")

    # Create Course Outcomes Table
    create_co_table = """
    CREATE TABLE IF NOT EXISTS course_outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text VARCHAR(500) NOT NULL,
        code VARCHAR(50),
        topic_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(topic_id) REFERENCES topics(id)
    );
    """
    cursor.execute(create_co_table)
    print("Created course_outcomes table.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
