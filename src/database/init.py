"""Initialize database tables.

Run: python -m src.database.init
"""

from database.connection import init_db

if __name__ == "__main__":
    init_db()
    print("Database tables created successfully.")
