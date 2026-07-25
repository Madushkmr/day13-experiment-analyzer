import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.stats_frequentist import two_proportion_z_test, welch_t_test_from_daily
from src.stats_bayesian import beta_binomial_analysis
from src.stats_sequential import msprt_sequential_test


def test_two_proportion_z_test_detects_clear_effect():
    # control 4% conversion, treatment 6% conversion, large samples -> significant
    result = two_proportion_z_test(400, 10000, 600, 10000)
    assert result["significant"] is True
    assert result["p_value"] < 0.05
    assert result["treatment_rate"] > result["control_rate"]


def test_two_proportion_z_test_no_effect():
    # identical rates -> not significant
    result = two_proportion_z_test(500, 10000, 505, 10000)
    assert result["significant"] is False
    assert result["p_value"] > 0.05


def test_two_proportion_z_test_requires_users():
    try:
        two_proportion_z_test(0, 0, 10, 100)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_welch_t_test_detects_revenue_lift():
    control_daily = [{"users": 100, "revenue": 100 + i} for i in range(10)]
    treat_daily = [{"users": 100, "revenue": 140 + i} for i in range(10)]
    result = welch_t_test_from_daily(control_daily, treat_daily)
    assert result["treatment_mean_rev_per_user"] > result["control_mean_rev_per_user"]
    assert result["significant"] is True


def test_beta_binomial_prefers_better_variant():
    result = beta_binomial_analysis(400, 10000, 600, 10000)
    assert result["prob_treatment_better"] > 0.95
    assert result["recommendation"] in ("ship_treatment", "keep_collecting_data")


def test_beta_binomial_symmetric_prior_no_effect():
    result = beta_binomial_analysis(500, 10000, 500, 10000)
    assert 0.3 < result["prob_treatment_better"] < 0.7


def test_msprt_stops_on_large_persistent_effect():
    daily_control = [{"users": 1000, "conversions": 40} for _ in range(30)]
    daily_treatment = [{"users": 1000, "conversions": 70} for _ in range(30)]
    result = msprt_sequential_test(daily_control, daily_treatment)
    assert result["can_stop"] is True
    assert result["decision"] == "treatment_better"
    assert result["stop_day"] is not None


def test_msprt_does_not_stop_with_no_effect():
    daily_control = [{"users": 200, "conversions": 10} for _ in range(15)]
    daily_treatment = [{"users": 200, "conversions": 10} for _ in range(15)]
    result = msprt_sequential_test(daily_control, daily_treatment)
    assert result["can_stop"] is False
    assert result["decision"] == "keep_collecting_data"
