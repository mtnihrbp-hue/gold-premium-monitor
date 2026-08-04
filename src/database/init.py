"""Initialize the database schema.

Usage:
    python -m database.init

Requires DATABASE_URL environment variable to be set.
"""

from database.connection import init_db

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
