"""
Create the approval_request table for the Designer Approval Workflow.
Idempotent: safe to run multiple times.
Run once after pulling the QA approval changes:

    python backend/scripts/migrate_add_approvals.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect

from app.database.db import Base, engine

# Import models so they register on Base.metadata
from app.database import models  # noqa: F401


def migrate():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if "approval_request" in existing_tables:
        print("Table already exists: approval_request")
        return

    ApprovalRequest = models.ApprovalRequest
    ApprovalRequest.__table__.create(bind=engine)
    print("Created table: approval_request")
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
