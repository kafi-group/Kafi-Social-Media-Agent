"""
Create the platform_credential table for durable OAuth token storage.
Idempotent: safe to run multiple times.

    python backend/scripts/migrate_add_platform_credentials.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect

from app.database.db import engine
from app.database import models  # noqa: F401


def migrate():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if "platform_credential" in existing_tables:
        print("Table already exists: platform_credential")
        return

    models.PlatformCredential.__table__.create(bind=engine)
    print("Created table: platform_credential")
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
