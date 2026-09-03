"""Apply db/SCHEMA.sql to Supabase.

Usage:  .venv/Scripts/python scripts/apply_schema.py

Reads DATABASE_URL from .env. SCHEMA.sql is idempotent, so re-running it is
safe and is the normal way to pick up a schema change.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402

SCHEMA = ROOT / "db" / "SCHEMA.sql"


def main() -> int:
    if not settings.DATABASE_URL:
        print(
            "DATABASE_URL is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Supabase dashboard -> Settings -> Database -> Connection string (URI)\n"
            "  3. Paste it as DATABASE_URL",
            file=sys.stderr,
        )
        return 2

    try:
        import psycopg
    except ImportError:
        print("Install the driver first:  .venv/Scripts/python -m pip install 'psycopg[binary]'",
              file=sys.stderr)
        return 2

    sql = SCHEMA.read_text(encoding="utf-8")
    print(f"Applying {SCHEMA.relative_to(ROOT)} ({len(sql):,} bytes) ...")

    with psycopg.connect(settings.DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

            cur.execute("""
                select count(*) from information_schema.tables
                where table_schema = 'public' and table_type = 'BASE TABLE'
            """)
            tables = cur.fetchone()[0]

            # Verify RLS is actually ON, not merely that policies were written.
            cur.execute("""
                select c.relname from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity
            """)
            unprotected = [r[0] for r in cur.fetchall()]

            cur.execute("select count(*) from pg_policies where schemaname = 'public'")
            policies = cur.fetchone()[0]

    print(f"  tables:   {tables}")
    print(f"  policies: {policies}")
    if unprotected:
        print(f"  WARNING - RLS is OFF on: {', '.join(unprotected)}")
        return 1
    print("  RLS: enabled on every table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
