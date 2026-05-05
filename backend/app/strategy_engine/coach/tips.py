"""Hinglish tip templates for every (metric, grade) cell.

ASCII-safe text — only ``%`` and ``₹`` are allowed beyond plain ASCII.
Tip strings deliberately keep punctuation simple (no en/em dashes, no
curly quotes) so the output round-trips through any UI / log layer
without re-encoding.

Each generator takes the user's value and returns one short tip
(typically 1-2 sentences). The numeric value is formatted in the tip
using ``%`` for percentage metrics and ``₹`` when describing money
loss / risk-reward. The CONCERNING tier for several metrics has a
``₹`` example so the operator sees the real-money impact.
"""

from __future__ import annotations

from app.strategy_engine.coach.models import MetricGradeLevel

# ─── Win Rate ──────────────────────────────────────────────────────────


def win_rate_tip(grade: MetricGradeLevel, value_pct: float) -> str:
    if grade == "EXCELLENT":
        return (
            f"Aapki strategy ne {value_pct:.1f}% baar profit kiya - sweet spot "
            "50-65% mein hai. Realistic aur sustainable."
        )
    if grade == "GOOD":
        return (
            f"Win rate {value_pct:.1f}% solid hai. Profit factor aur RR ke "
            "saath dekho overall picture clear hoga."
        )
    if grade == "ACCEPTABLE":
        return (
            f"Win rate {value_pct:.1f}% theek hai. Average win bada hai toh ye "
            "bhi profitable ho sakti hai - RR check karo."
        )
    # CONCERNING
    if value_pct > 85.0:
        return (
            f"{value_pct:.1f}% bahut zyada hai - real markets mein sustainable "
            "nahi, overfitting ka sign."
        )
    return (
        f"Win rate {value_pct:.1f}% kam hai (40-65% target). Strategy ke entry "
        "rules tighten karo ya RR badhao."
    )


# ─── Profit Factor ─────────────────────────────────────────────────────


def profit_factor_tip(grade: MetricGradeLevel, value: float) -> str:
    if grade == "EXCELLENT":
        if value == float("inf"):
            return (
                "Profit factor infinite hai - zero losses (suspicious if real "
                "data). Verify trade count aur sample period."
            )
        return (
            f"Profit factor {value:.2f}x excellent hai. Aap ₹1 risk leke "
            f"₹{value:.2f} kama rahe ho on average."
        )
    if grade == "GOOD":
        return (
            f"Profit factor {value:.2f}x achha hai. Aap ₹1 risk leke "
            f"₹{value:.2f} kama rahe ho. >2.0 excellent hota hai."
        )
    if grade == "ACCEPTABLE":
        return (
            f"Profit factor {value:.2f}x marginal hai. Costs aur slippage "
            "badhe toh negative ho sakta hai - 1.5+ aim karo."
        )
    return (
        f"Profit factor {value:.2f}x kam hai - strategy losses cover nahi kar "
        "pa rahi. Entry/exit rules re-check karo."
    )


# ─── Max Drawdown ──────────────────────────────────────────────────────


def max_drawdown_tip(grade: MetricGradeLevel, value_pct: float) -> str:
    if grade == "EXCELLENT":
        return (
            f"Max drawdown {value_pct:.1f}% kam hai - position sizing bilkul "
            "sahi hai. Capital safe rehta hai loss periods mein."
        )
    if grade == "GOOD":
        return (
            f"Drawdown {value_pct:.1f}% manageable hai. Stop loss strict "
            "rakho, position size bada mat karo."
        )
    if grade == "ACCEPTABLE":
        return (
            f"Drawdown {value_pct:.1f}% high side pe hai. Risk per trade kam "
            "karo - 1-2% capital max."
        )
    # CONCERNING — concrete rupee example so the loss feels real.
    rs_per_100 = round(value_pct)
    return (
        f"Worst loss period mein {value_pct:.1f}% gawaaya - har ₹100 par "
        f"~₹{rs_per_100} loss. Zyada hai, <15% ideal."
    )


# ─── Risk-Reward ───────────────────────────────────────────────────────


def risk_reward_tip(grade: MetricGradeLevel, value: float) -> str:
    if grade == "EXCELLENT":
        if value == float("inf"):
            return (
                "RR infinite hai - no losses. Sample size verify karo before "
                "trusting this."
            )
        return (
            f"RR {value:.2f}x excellent. Average winner average loser se "
            f"{value:.1f}x bada hai - strong edge."
        )
    if grade == "GOOD":
        return (
            f"RR {value:.2f}x achha hai. Aap har ₹1 risk leke ₹{value:.2f} "
            "kama rahe ho on average."
        )
    if grade == "ACCEPTABLE":
        return (
            f"RR {value:.2f}x ok hai but tight. Stop loss thoda tighter ya "
            "target wider karo."
        )
    return (
        f"Average loss average win se bada hai (RR {value:.2f}x). Stop loss "
        "tighter ya target wider karo."
    )


# ─── Total Trades ──────────────────────────────────────────────────────


def total_trades_tip(grade: MetricGradeLevel, count: int) -> str:
    if grade == "EXCELLENT":
        return (
            f"{count} trades aapko statistically confident banata hai. "
            "Sample size strong hai."
        )
    if grade == "GOOD":
        return (
            f"{count} trades decent hai. Aur thoda data lo confidence ke "
            "liye - 100+ best."
        )
    if grade == "ACCEPTABLE":
        return (
            f"{count} trades workable but borderline. 50+ chahiye reliable "
            "conclusions ke liye."
        )
    return (
        f"Sirf {count} trades - sample chhota hai, results luck-based ho "
        "sakte hain. Longer period par test karo."
    )


# ─── Expectancy ────────────────────────────────────────────────────────


def expectancy_tip(grade: MetricGradeLevel, value_pct: float) -> str:
    if grade == "EXCELLENT":
        return (
            f"Har trade par average {value_pct:.2f}% capital ka profit. "
            "Strong edge - har ₹100 par ~₹"
            f"{value_pct:.2f} per trade."
        )
    if grade == "GOOD":
        return (
            f"Expectancy positive {value_pct:.2f}% per trade hai. Choti edge "
            "but real edge hai."
        )
    if grade == "ACCEPTABLE":
        return (
            f"Expectancy lagbhag zero hai ({value_pct:.2f}% per trade). Edge "
            "weak hai - costs eat karenge."
        )
    return (
        f"Negative expectancy: har trade par average {value_pct:.2f}% loss - "
        f"~₹{abs(value_pct):.2f} loss per ₹100. Strategy abhi profitable nahi."
    )


# ─── Recovery Factor ───────────────────────────────────────────────────


def recovery_factor_tip(grade: MetricGradeLevel, value: float) -> str:
    if grade == "EXCELLENT":
        if value == float("inf"):
            return (
                "Recovery infinite hai - profit with zero drawdown. Verify "
                "data aur sample size."
            )
        return (
            f"Recovery factor {value:.1f}x excellent. Profit drawdown se "
            f"{value:.1f} guna bada."
        )
    if grade == "GOOD":
        return (
            f"Recovery factor {value:.1f}x achha hai. Loss periods se "
            "nikalne ki kshamta strong hai."
        )
    if grade == "ACCEPTABLE":
        return (
            f"Recovery factor {value:.1f}x ok hai. Drawdown ke baad recover "
            "hota hai but slowly."
        )
    return (
        f"Recovery factor {value:.1f}x kam hai - drawdown ke comparison mein "
        "returns weak hai. Risk badha kar reward thoda bhi nahi mil raha."
    )


__all__ = [
    "expectancy_tip",
    "max_drawdown_tip",
    "profit_factor_tip",
    "recovery_factor_tip",
    "risk_reward_tip",
    "total_trades_tip",
    "win_rate_tip",
]
