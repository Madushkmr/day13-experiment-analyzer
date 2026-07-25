"""Convenience script: initializes the DB and loads the sample dataset.

Run once before starting the dashboard:
  python seed.py
  python app.py
"""
from src.ingest import ingest_csv

if __name__ == "__main__":
    result = ingest_csv("sample_data/experiments_daily.csv")
    print(f"Seeded {result['rows_loaded']} rows across experiments: {', '.join(result['experiments'])}")
