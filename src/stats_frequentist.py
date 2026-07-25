"""Frequentist hypothesis tests for A/B experiment analysis.

Two metric types are supported:
  - conversion: two-proportion z-test (control conversion rate vs. treatment)
  - revenue: Welch's t-test on per-user revenue (approximated from aggregate
    totals using a normal approximation, since we only persist daily totals
    rather than raw per-user rows)
"""
import math
from scipy import stats as scipy_stats


def two_proportion_z_test(control_conversions, control_users, treat_conversions, treat_users, alpha=0.05):
    if control_users == 0 or treat_users == 0:
        raise ValueError("Both variants need at least 1 user")

    p1 = control_conversions / control_users
    p2 = treat_conversions / treat_users
    pooled = (control_conversions + treat_conversions) / (control_users + treat_users)

    se = math.sqrt(pooled * (1 - pooled) * (1 / control_users + 1 / treat_users))
    if se == 0:
        z = 0.0
    else:
        z = (p2 - p1) / se

    p_value = float(2 * (1 - scipy_stats.norm.cdf(abs(z))))
    lift = (p2 - p1) / p1 if p1 > 0 else float("inf") if p2 > 0 else 0.0

    # Wald 95% CI on the difference in proportions
    se_diff = math.sqrt(p1 * (1 - p1) / control_users + p2 * (1 - p2) / treat_users)
    z_crit = float(scipy_stats.norm.ppf(1 - alpha / 2))
    ci_low = (p2 - p1) - z_crit * se_diff
    ci_high = (p2 - p1) + z_crit * se_diff

    return {
        "test": "two_proportion_z_test",
        "control_rate": round(p1, 5),
        "treatment_rate": round(p2, 5),
        "relative_lift": round(lift, 5),
        "z_score": round(z, 4),
        "p_value": round(p_value, 6),
        "significant": bool(p_value < alpha),
        "alpha": alpha,
        "diff_ci_95": [round(ci_low, 5), round(ci_high, 5)],
    }


def welch_t_test_from_daily(control_daily, treat_daily, alpha=0.05):
    """Welch's t-test comparing mean revenue-per-user-day between variants.

    control_daily / treat_daily: list of dicts with 'users' and 'revenue' for
    each day. We treat each day's revenue-per-user as one sample point, which
    is a reasonable approximation for a daily-aggregated dataset.
    """
    c_vals = [d["revenue"] / d["users"] for d in control_daily if d["users"] > 0]
    t_vals = [d["revenue"] / d["users"] for d in treat_daily if d["users"] > 0]

    if len(c_vals) < 2 or len(t_vals) < 2:
        raise ValueError("Need at least 2 days of data per variant for a t-test")

    t_stat, p_value = scipy_stats.ttest_ind(t_vals, c_vals, equal_var=False)
    mean_c = sum(c_vals) / len(c_vals)
    mean_t = sum(t_vals) / len(t_vals)
    lift = (mean_t - mean_c) / mean_c if mean_c > 0 else float("inf") if mean_t > 0 else 0.0

    return {
        "test": "welch_t_test",
        "control_mean_rev_per_user": round(mean_c, 4),
        "treatment_mean_rev_per_user": round(mean_t, 4),
        "relative_lift": round(lift, 5),
        "t_statistic": round(float(t_stat), 4),
        "p_value": round(float(p_value), 6),
        "significant": bool(p_value < alpha),
        "alpha": alpha,
        "n_days_control": len(c_vals),
        "n_days_treatment": len(t_vals),
    }
