"""Sequential (always-valid) testing for conversion metrics.

Implements a mixture-based sequential probability ratio test (mSPRT) using a
normal mixture over the log-odds difference. Unlike a fixed-horizon z-test,
the resulting p-value stays valid no matter when you peek at it, which is
what makes "sequential" testing safe for BI dashboards that get checked
daily rather than only once at a pre-committed sample size.

Reference approach: Johari, Koomen, Pekelis, Walsh (2017), "Peeking at
A/B Tests" - simplified for a single mixture variance rather than a full
adaptive design, which keeps the implementation compact.
"""
import math


def _log_odds(p, eps=1e-6):
    p = min(max(p, eps), 1 - eps)
    return math.log(p / (1 - p))


def msprt_sequential_test(daily_control, daily_treatment, tau=1.0, alpha=0.05):
    """Run a day-by-day mSPRT over cumulative conversion data.

    daily_control / daily_treatment: lists of {'users', 'conversions'} dicts,
    one entry per day, in chronological order (same length not required).
    tau: mixture prior variance on the effect size (log-odds scale). Larger
    tau assumes bigger expected effects; 1.0 is a reasonable default for
    typical BI conversion-rate experiments.

    Returns the full daily trajectory of the mixture likelihood ratio plus
    the first day (if any) the test could stop.
    """
    trajectory = []
    cum_c_users = cum_c_conv = 0
    cum_t_users = cum_t_conv = 0

    max_days = max(len(daily_control), len(daily_treatment))
    stop_day = None
    stop_decision = None
    threshold = 1 / alpha  # likelihood ratio threshold for always-valid inference

    for i in range(max_days):
        if i < len(daily_control):
            cum_c_users += daily_control[i]["users"]
            cum_c_conv += daily_control[i]["conversions"]
        if i < len(daily_treatment):
            cum_t_users += daily_treatment[i]["users"]
            cum_t_conv += daily_treatment[i]["conversions"]

        if cum_c_users == 0 or cum_t_users == 0:
            trajectory.append({"day": i, "mixture_lr": 1.0, "cum_users_control": cum_c_users, "cum_users_treatment": cum_t_users})
            continue

        p_c = cum_c_conv / cum_c_users
        p_t = cum_t_conv / cum_t_users
        theta_hat = _log_odds(p_t) - _log_odds(p_c)

        # Fisher information approximation for log-odds difference
        var_c = 1 / (cum_c_users * max(p_c * (1 - p_c), 1e-6))
        var_t = 1 / (cum_t_users * max(p_t * (1 - p_t), 1e-6))
        v = var_c + var_t

        # Normal-mixture likelihood ratio (closed form for a N(0, tau^2) mixture prior)
        lr = math.sqrt(v / (v + tau)) * math.exp((tau * theta_hat ** 2) / (2 * v * (v + tau)))

        trajectory.append(
            {
                "day": i,
                "mixture_lr": round(lr, 4),
                "theta_hat": round(theta_hat, 4),
                "cum_users_control": cum_c_users,
                "cum_users_treatment": cum_t_users,
            }
        )

        if stop_day is None and lr >= threshold:
            stop_day = i
            stop_decision = "treatment_better" if theta_hat > 0 else "control_better"

    return {
        "test": "msprt_sequential",
        "alpha": alpha,
        "tau": tau,
        "stop_threshold_lr": round(threshold, 2),
        "can_stop": stop_day is not None,
        "stop_day": stop_day,
        "decision": stop_decision or "keep_collecting_data",
        "final_mixture_lr": trajectory[-1]["mixture_lr"] if trajectory else None,
        "trajectory": trajectory,
    }
