"""
Migration: Add review_token_expires_at to approval_request table

Run once after deploying the security hardening update:

    cd backend
    python scripts/migrate_add_token_expiry.py

This is a safe, additive migration (ALTER TABLE … ADD COLUMN IF NOT EXISTS).
Existing rows will have NULL expiry (they will be accepted by the review
endpoint until you choose to enforce back-fills via a separate script).
"""

import sys
from pathlib import Path

# Allow importing app modules when run from the backend directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.utils.logger import logger


def run() -> None:
    import sqlalchemy as sa

    engine = sa.create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # Check if the column already exists
        inspector = sa.inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("approval_request")]

        if "review_token_expires_at" in columns:
            print("Column review_token_expires_at already exists — nothing to do.")
            return

        print("Adding column review_token_expires_at to approval_request …")
        conn.execute(
            sa.text(
                "ALTER TABLE approval_request "
                "ADD COLUMN review_token_expires_at TIMESTAMP WITHOUT TIME ZONE"
            )
        )
        conn.commit()
        print("Done.")


if __name__ == "__main__":
    run()
