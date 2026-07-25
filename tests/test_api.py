import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src import db as db_module


@pytest.fixture()
def client(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("EXPERIMENT_DB_PATH", path)
    monkeypatch.setattr(db_module, "DB_PATH", path)

    import app as app_module
    monkeypatch.setattr(app_module.db, "DB_PATH", path)
    app_module.db.init_db(path)
    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as c:
        yield c

    os.remove(path)


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_create_and_list_experiment(client):
    res = client.post("/api/experiments", json={"name": "button_color", "metric_type": "conversion"})
    assert res.status_code == 201
    exp = res.get_json()
    assert exp["name"] == "button_color"

    res = client.get("/api/experiments")
    assert res.status_code == 200
    assert len(res.get_json()) == 1


def test_duplicate_experiment_rejected(client):
    client.post("/api/experiments", json={"name": "dup_test", "metric_type": "conversion"})
    res = client.post("/api/experiments", json={"name": "dup_test", "metric_type": "conversion"})
    assert res.status_code == 409


def test_add_observation_and_analyze(client):
    res = client.post("/api/experiments", json={"name": "signup_flow", "metric_type": "conversion"})
    exp_id = res.get_json()["id"]

    for day in range(1, 6):
        client.post(
            f"/api/experiments/{exp_id}/observations",
            json={"variant": "control", "day": day, "users": 500, "conversions": 25},
        )
        client.post(
            f"/api/experiments/{exp_id}/observations",
            json={"variant": "treatment", "day": day, "users": 500, "conversions": 40},
        )

    res = client.get(f"/api/experiments/{exp_id}/analysis")
    assert res.status_code == 200
    report = res.get_json()
    assert report["frequentist"]["significant"] is True
    assert report["bayesian"]["prob_treatment_better"] > 0.5
    assert "sequential" in report


def test_analysis_missing_treatment_returns_error(client):
    res = client.post("/api/experiments", json={"name": "control_only", "metric_type": "conversion"})
    exp_id = res.get_json()["id"]
    client.post(
        f"/api/experiments/{exp_id}/observations",
        json={"variant": "control", "day": 1, "users": 100, "conversions": 5},
    )
    res = client.get(f"/api/experiments/{exp_id}/analysis")
    assert res.status_code == 200
    assert "error" in res.get_json()


def test_analysis_unknown_experiment_404(client):
    res = client.get("/api/experiments/9999/analysis")
    assert res.status_code == 404
