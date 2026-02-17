from database import engine, Base
from models import VettedQuestion, Skill, TrainingRun

def migrate_vetted_db():
    print("Migrating Vetted Question & Training tables...")
    # Create new tables
    Base.metadata.create_all(bind=engine)
    print("Migration complete!")

if __name__ == "__main__":
    migrate_vetted_db()
