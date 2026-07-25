"""Bayesian A/B testing via Beta-Binomial conjugate model.

For conversion metrics we model each variant's conversion rate as a Beta
posterior (Beta(1,1) uninformative prior updated with observed
conversions/non-conversions), then estimate:
  - P(treatment > control) via Monte Carlo sampling
  - expected loss of choosing the treatment if it's actually worse
    (a standard decision-theoretic stopping rule for Bayesian A/B tests)
"""
import numpy as np


def beta_binomial_analysis(
    control_conversions,
    control_users,
    treat_conversions,
    treat_users,
    prior_alpha=1.0,
    prior_beta=1.0,
    n_samples=200_000,
    seed=42,
):
    if control_users == 0 or treat_users == 0:
        raise ValueError("Both variants need at least 1 user")

    rng = np.random.default_rng(seed)

    a_c = prior_alpha + control_conversions
    b_c = prior_beta + (control_users - control_conversions)
    a_t = prior_alpha + treat_conversions
    b_t = prior_beta + (treat_users - treat_conversions)

    control_samples = rng.beta(a_c, b_c, n_samples)
    treat_samples = rng.beta(a_t, b_t, n_samples)

    prob_treat_better = float(np.mean(treat_samples > control_samples))

    # Expected loss: how much conversion rate you'd give up, on average, by
    # picking the "wrong" variant. Standard Bayesian A/B stopping criterion.
    loss_if_choose_treat = np.mean(np.maximum(control_samples - treat_samples, 0))
    loss_if_choose_control = np.mean(np.maximum(treat_samples - control_samples, 0))

    diff = treat_samples - control_samples
    ci_low, ci_high = np.percentile(diff, [2.5, 97.5])

    return {
        "test": "beta_binomial_bayesian",
        "control_posterior_mean": round(a_c / (a_c + b_c), 5),
        "treatment_posterior_mean": round(a_t / (a_t + b_t), 5),
        "prob_treatment_better": round(prob_treat_better, 5),
        "expected_loss_choosing_treatment": round(float(loss_if_choose_treat), 6),
        "expected_loss_choosing_control": round(float(loss_if_choose_control), 6),
        "diff_credible_interval_95": [round(float(ci_low), 5), round(float(ci_high), 5)],
        "recommendation": _recommend(prob_treat_better, loss_if_choose_treat, loss_if_choose_control),
    }


def _recommend(prob_treat_better, loss_treat, loss_control, loss_threshold=0.0025):
    """Simple decision rule: ship treatment once its expected loss is below a
    small tolerance threshold (a common practical heuristic in Bayesian A/B
    testing) and it's favored by posterior probability."""
    if loss_treat <= loss_threshold and prob_treat_better >= 0.5:
        return "ship_treatment"
    if loss_control <= loss_threshold and prob_treat_better < 0.5:
        return "keep_control"
    return "keep_collecting_data"
