"""SQLite persistence layer for the experiment analyzer.

Schema:
  experiments(id, name, metric_type, created_at)
  observations(id, experiment_id, variant, day, users, conversions, revenue)

metric_type is either 'conversion' (binary conversion-rate metric) or
'revenue' (continuous revenue-per-user metric). Both stat modules read from
the same observations table.
"""
import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "EXPERIMENT_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "experiments.db"),
)


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    conn = get_connection(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            metric_type TEXT NOT NULL CHECK(metric_type IN ('conversion', 'revenue')),
            control_variant TEXT NOT NULL DEFAULT 'control',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
            variant TEXT NOT NULL,
            day INTEGER NOT NULL,
            users INTEGER NOT NULL,
            conversions INTEGER NOT NULL DEFAULT 0,
            revenue REAL NOT NULL DEFAULT 0,
            UNIQUE(experiment_id, variant, day)
        );

        CREATE INDEX IF NOT EXISTS idx_obs_experiment ON observations(experiment_id);
        """
    )
    conn.commit()
    conn.close()


def create_experiment(name, metric_type, control_variant="control", db_path=None):
    conn = get_connection(db_path)
    cur = conn.execute(
        "INSERT INTO experiments (name, metric_type, control_variant, created_at) VALUES (?, ?, ?, ?)",
        (name, metric_type, control_variant, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    exp_id = cur.lastrowid
    conn.close()
    return exp_id


def get_experiment_by_name(name, db_path=None):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM experiments WHERE name = ?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_experiment(experiment_id, db_path=None):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_experiments(db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_observation(experiment_id, variant, day, users, conversions=0, revenue=0.0, db_path=None):
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO observations (experiment_id, variant, day, users, conversions, revenue)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(experiment_id, variant, day) DO UPDATE SET
               users=excluded.users, conversions=excluded.conversions, revenue=excluded.revenue""",
        (experiment_id, variant, day, users, conversions, revenue),
    )
    conn.commit()
    conn.close()


def get_observations(experiment_id, db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM observations WHERE experiment_id = ? ORDER BY variant, day",
        (experiment_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_variant_totals(experiment_id, db_path=None):
    """Aggregate totals per variant, cumulative and per-day series."""
    obs = get_observations(experiment_id, db_path)
    variants = {}
    for row in obs:
        v = row["variant"]
        variants.setdefault(v, {"users": 0, "conversions": 0, "revenue": 0.0, "daily": []})
        variants[v]["users"] += row["users"]
        variants[v]["conversions"] += row["conversions"]
        variants[v]["revenue"] += row["revenue"]
        variants[v]["daily"].append(
            {
                "day": row["day"],
                "users": row["users"],
                "conversions": row["conversions"],
                "revenue": row["revenue"],
            }
        )
    return variants
