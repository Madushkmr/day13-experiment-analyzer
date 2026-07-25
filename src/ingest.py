"""CSV ingestion: loads daily per-variant experiment metrics into SQLite.

Expected CSV columns: experiment,metric_type,variant,day,users,conversions,revenue
One row per (experiment, variant, day). `conversions` and `revenue` may be
left blank/0 for metrics that don't apply.
"""
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import db


def ingest_csv(csv_path, db_path=None):
    db.init_db(db_path)
    seen_experiments = {}
    rows_loaded = 0

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            exp_name = row["experiment"].strip()
            metric_type = row["metric_type"].strip()

            if exp_name not in seen_experiments:
                existing = db.get_experiment_by_name(exp_name, db_path)
                if existing:
                    exp_id = existing["id"]
                else:
                    exp_id = db.create_experiment(exp_name, metric_type, db_path=db_path)
                seen_experiments[exp_name] = exp_id

            db.add_observation(
                experiment_id=seen_experiments[exp_name],
                variant=row["variant"].strip(),
                day=int(row["day"]),
                users=int(row["users"]),
                conversions=int(row.get("conversions") or 0),
                revenue=float(row.get("revenue") or 0.0),
                db_path=db_path,
            )
            rows_loaded += 1

    return {"experiments": list(seen_experiments.keys()), "rows_loaded": rows_loaded}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "sample_data/experiments_daily.csv"
    result = ingest_csv(path)
    print(f"Loaded {result['rows_loaded']} rows across experiments: {', '.join(result['experiments'])}")
