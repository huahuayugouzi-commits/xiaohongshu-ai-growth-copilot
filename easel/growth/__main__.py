"""python -m easel.growth [--db PATH]: initialize/check without changing existing Easel storage."""

import argparse
from contextlib import closing

from .database import Database


def main():
    parser = argparse.ArgumentParser(description="Initialize Growth Copilot SQLite data layer")
    parser.add_argument("--db", help="Overrides GROWTH_DB_PATH and the project-local default")
    args = parser.parse_args()
    database = Database(args.db)
    database.initialize()
    with closing(database.connect()) as conn:
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Growth database has foreign key violations")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Growth database integrity check failed")
    print(f"Growth Copilot database ready: {database.path}")


if __name__ == "__main__":
    main()
