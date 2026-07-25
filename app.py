"""Flask REST API + dashboard for the A/B Test & Experimentation Analyzer.

Endpoints:
  GET  /                                  -> HTML dashboard
  GET  /api/experiments                   -> list all experiments
  POST /api/experiments                   -> create an experiment
  POST /api/experiments/<id>/observations -> add/update a daily observation
  GET  /api/experiments/<id>/analysis     -> frequentist + bayesian + sequential report
  GET  /api/health                        -> health check

Run:
  python app.py
  # then visit http://localhost:5000
"""
import os
from flask import Flask, jsonify, request, render_template

from src import db
from src.stats_frequentist import two_proportion_z_test, welch_t_test_from_daily
from src.stats_bayesian import beta_binomial_analysis
from src.stats_sequential import msprt_sequential_test

app = Flask(__name__)


def _build_analysis(experiment):
    exp_id = experiment["id"]
    metric_type = experiment["metric_type"]
    control_variant = experiment["control_variant"]
    variants = db.get_variant_totals(exp_id)

    other_variants = [v for v in variants if v != control_variant]
    if control_variant not in variants or not other_variants:
        return {"error": "Need observations for both a control and at least one treatment variant"}

    treat_variant = other_variants[0]
    control = variants[control_variant]
    treat = variants[treat_variant]

    report = {
        "experiment": experiment["name"],
        "metric_type": metric_type,
        "control_variant": control_variant,
        "treatment_variant": treat_variant,
        "control_totals": {"users": control["users"], "conversions": control["conversions"], "revenue": round(control["revenue"], 2)},
        "treatment_totals": {"users": treat["users"], "conversions": treat["conversions"], "revenue": round(treat["revenue"], 2)},
    }

    if metric_type == "conversion":
        report["frequentist"] = two_proportion_z_test(
            control["conversions"], control["users"], treat["conversions"], treat["users"]
        )
        report["bayesian"] = beta_binomial_analysis(
            control["conversions"], control["users"], treat["conversions"], treat["users"]
        )
        report["sequential"] = msprt_sequential_test(control["daily"], treat["daily"])
    else:
        report["frequentist"] = welch_t_test_from_daily(control["daily"], treat["daily"])
        report["bayesian"] = None
        report["sequential"] = None

    return report


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/experiments", methods=["GET"])
def list_experiments():
    return jsonify(db.list_experiments())


@app.route("/api/experiments", methods=["POST"])
def create_experiment():
    payload = request.get_json(force=True)
    name = payload.get("name")
    metric_type = payload.get("metric_type")
    control_variant = payload.get("control_variant", "control")

    if not name or metric_type not in ("conversion", "revenue"):
        return jsonify({"error": "name and metric_type ('conversion'|'revenue') are required"}), 400

    if db.get_experiment_by_name(name):
        return jsonify({"error": f"experiment '{name}' already exists"}), 409

    exp_id = db.create_experiment(name, metric_type, control_variant)
    return jsonify(db.get_experiment(exp_id)), 201


@app.route("/api/experiments/<int:experiment_id>/observations", methods=["POST"])
def add_observation(experiment_id):
    experiment = db.get_experiment(experiment_id)
    if not experiment:
        return jsonify({"error": "experiment not found"}), 404

    payload = request.get_json(force=True)
    required = ["variant", "day", "users"]
    if any(f not in payload for f in required):
        return jsonify({"error": f"required fields: {required}"}), 400

    db.add_observation(
        experiment_id=experiment_id,
        variant=payload["variant"],
        day=int(payload["day"]),
        users=int(payload["users"]),
        conversions=int(payload.get("conversions", 0)),
        revenue=float(payload.get("revenue", 0.0)),
    )
    return jsonify({"status": "recorded"}), 201


@app.route("/api/experiments/<int:experiment_id>/analysis", methods=["GET"])
def analyze_experiment(experiment_id):
    experiment = db.get_experiment(experiment_id)
    if not experiment:
        return jsonify({"error": "experiment not found"}), 404
    try:
        return jsonify(_build_analysis(experiment))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/")
def dashboard():
    experiments = db.list_experiments()
    return render_template("dashboard.html", experiments=experiments)


if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
