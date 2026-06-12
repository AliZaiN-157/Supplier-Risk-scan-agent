"""Pure risk scoring functions per §3 of the PRD.

All functions are deterministic (no hardcoded final scores).
Higher score = higher risk (0 = no risk, 100 = max risk).
"""
from __future__ import annotations
from app.models import RiskLevel, Trend

# Dimension weights from §3.1
WEIGHT_FINANCIAL = 0.30
WEIGHT_OPERATIONAL = 0.25
WEIGHT_COMPLIANCE = 0.20
WEIGHT_GEOPOLITICAL = 0.15
WEIGHT_ESG = 0.10


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp a value between low and high."""
    return max(low, min(high, value))


def compute_financial_score(
    credit_score: int,
    profit_margin: float,
    dso: float,
    debt_ratio: float,
) -> float:
    """
    Compute financial risk score (0-100).

    Inputs:
      credit_score:  300-850 (higher = better → invert)
      profit_margin: -5% to +25% (negative → +20 penalty)
      dso:           20-120 days (>90 → +15 penalty)
      debt_ratio:    0-1+ (higher = worse)

    Returns 0-100 float.
    """
    # Invert credit score: 850→0 risk, 300→100 risk base
    credit_risk = 100.0 * (850 - credit_score) / 550.0

    # Profit margin score: 25%→0 risk, -5%→100 risk base
    margin_risk = 100.0 * (25.0 - profit_margin) / 30.0

    # Penalty for negative margin
    if profit_margin < 0:
        margin_risk += 20

    # DSO risk: lower is better, 20→0, 120→100
    dso_risk = 100.0 * (dso - 20.0) / 100.0

    # Penalty for DSO > 90
    if dso > 90:
        dso_risk += 15

    # Debt ratio risk: 0→0, 1→100
    debt_risk = 100.0 * debt_ratio

    # Weighted average of components
    score = (
        0.35 * credit_risk
        + 0.20 * margin_risk
        + 0.20 * dso_risk
        + 0.25 * debt_risk
    )
    return round(clamp(score), 1)


def compute_operational_score(
    on_time_delivery_pct: float,
    defect_rate_pct: float,
    capacity_utilization_pct: float,
) -> float:
    """
    Compute operational risk score (0-100).

    Inputs:
      on_time_delivery_pct: 60-99% (<80% → +20 penalty)
      defect_rate_pct:      0.1-8% (>3% → +15 penalty)
      capacity_utilization_pct: 0-100% (low util is risk)
    """
    # OTD risk: 99%→0, 60%→100
    otd_risk = 100.0 * (99.0 - on_time_delivery_pct) / 39.0

    # Penalty for OTD below 80%
    if on_time_delivery_pct < 80:
        otd_risk += 20

    # Defect risk: 0.1%→0, 8%→100
    defect_risk = 100.0 * (defect_rate_pct - 0.1) / 7.9

    # Penalty for defect rate above 3%
    if defect_rate_pct > 3.0:
        defect_risk += 15

    # Capacity utilization: 100%→0, 30%→100
    cap_risk = 100.0 * (100.0 - capacity_utilization_pct) / 70.0

    score = (
        0.40 * otd_risk
        + 0.30 * defect_risk
        + 0.30 * cap_risk
    )
    return round(clamp(score), 1)


def compute_compliance_score(
    violations_last_12mo: int,
    cert_expiry_days: int,
) -> float:
    """
    Compute compliance risk score (0-100).

    Inputs:
      violations_last_12mo: count of violations (>0 = risk)
      cert_expiry_days:     days until cert expiry (<60 → +25 penalty)
    """
    # Violations risk: 0→0, 5→100
    vio_risk = clamp(100.0 * violations_last_12mo / 5.0)

    # Cert expiry risk: 900 days→0, 0 days→100
    cert_risk = 100.0 * (900.0 - cert_expiry_days) / 900.0

    # Penalty for expiry within 60 days
    penalty = 25.0 if cert_expiry_days <= 60 else 0.0

    score = 0.50 * vio_risk + 0.50 * cert_risk + penalty
    return round(clamp(score), 1)


def compute_geo_score(
    country_risk_index: float,
    trade_restrictions: bool = False,
) -> float:
    """
    Compute geopolitical risk score (0-100).

    Inputs:
      country_risk_index: 0-100 from hardcoded dict
      trade_restrictions: True if active restrictions exist
    """
    score = country_risk_index
    if trade_restrictions:
        score += 20
    return round(clamp(score), 1)


def compute_esg_score(
    environmental: float,
    social: float,
    governance: float,
) -> float:
    """
    Compute ESG risk score (0-100). Average of three sub-scores.

    Inputs:
      environmental: 0-100
      social:        0-100
      governance:    0-100
    """
    score = (environmental + social + governance) / 3.0
    return round(clamp(score), 1)


def compute_overall_score(
    financial: float,
    operational: float,
    compliance: float,
    geo: float,
    esg: float,
) -> float:
    """
    Compute weighted overall risk score per §3.1.

    overall_score = 0.30·F + 0.25·O + 0.20·C + 0.15·G + 0.10·E
    """
    score = (
        WEIGHT_FINANCIAL * financial
        + WEIGHT_OPERATIONAL * operational
        + WEIGHT_COMPLIANCE * compliance
        + WEIGHT_GEOPOLITICAL * geo
        + WEIGHT_ESG * esg
    )
    return round(clamp(score), 1)


def determine_risk_level(overall_score: float) -> RiskLevel:
    """
    Determine risk level per §3.2 thresholds.

    LOW:      0-39
    MEDIUM:  40-59
    HIGH:    60-74
    CRITICAL: 75-100
    """
    if overall_score >= 75:
        return RiskLevel.CRITICAL
    elif overall_score >= 60:
        return RiskLevel.HIGH
    elif overall_score >= 40:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def determine_trend(history: list[float]) -> Trend:
    """
    Determine trend based on 30-day history.

    Compares average of last 7 days vs previous 7 days.
    - Recent lower → IMPROVING (risk decreasing)
    - Recent higher → DETERIORATING (risk increasing)
    - Within 2% → STABLE
    """
    if len(history) < 14:
        return Trend.STABLE

    recent = sum(history[-7:]) / 7.0
    previous = sum(history[-14:-7]) / 7.0

    diff = recent - previous
    threshold = 0.02 * previous  # 2% threshold

    if diff > threshold:
        return Trend.DETERIORATING
    elif diff < -threshold:
        return Trend.IMPROVING
    else:
        return Trend.STABLE
