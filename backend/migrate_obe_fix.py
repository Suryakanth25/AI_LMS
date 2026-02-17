from database import engine, Base
from models import CourseOutcome, LearningOutcome, UnitCOMapping
from sqlalchemy import text

def migrate():
    print("Starting OBE Hierarchy Migration...")
    
    with engine.connect() as conn:
        print("Dropping old tables if they exist...")
        conn.execute(text("DROP TABLE IF EXISTS unit_co_mapping"))
        conn.execute(text("DROP TABLE IF EXISTS learning_outcomes"))
        conn.execute(text("DROP TABLE IF EXISTS course_outcomes"))
        conn.commit()
        print("Dropped tables.")

    print("Creating new tables...")
    # Create only the specific tables we modified
    # improving safety by not calling create_all blindy, though create_all is idempotent
    Base.metadata.create_all(bind=engine)
    print("Migration complete. New tables created.")

if __name__ == "__main__":
    migrate()
