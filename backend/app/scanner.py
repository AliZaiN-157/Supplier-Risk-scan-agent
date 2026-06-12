"""Background risk scanner — real-time supplier monitoring engine.

Runs as an asyncio background task during the application lifespan.
Periodically tweaks supplier dimension scores (simulating real-world drift),
checks for threshold crossings, generates LLM-powered alerts via OpenRouter,
and pushes events to all WebSocket clients.

Architecture:
  [Scanner] → tweaks scores → checks thresholds → calls OpenRouter
       ↓                                        ↓
  broadcast score_update              creates Alert + broadcast new_alert
"""
from __future__ import annotations
import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.models import (
    Alert, Dimension, RiskLevel, Severity, Trend,
)
from app.risk_scorer import (
    compute_overall_score, determine_risk_level, determine_trend,
)

if TYPE_CHECKING:
    from app.ws_manager import WSManager
    from app.alert_engine import AlertEngine

logger = logging.getLogger(__name__)

# Scanning interval (seconds)
SCAN_INTERVAL_SECONDS = 8

# How much a dimension score can change per scan (±) — bigger = faster threshold crossing
SCORE_DELTA_RANGE = (-12.0, 12.0)

# How many suppliers to scan per cycle — more = more activity on screen
SUPPLIERS_PER_CYCLE = 3

# How many dimensions to tweak per supplier — more = more alert chances
DIMS_PER_SUPPLIER = 3

# Dimensions with their key names for score access
DIMENSION_KEYS = [
    "financial_score",
    "operational_score",
    "compliance_score",
    "geo_score",
    "esg_score",
]

DIMENSION_MAP: dict[str, Dimension] = {
    "financial_score": Dimension.FINANCIAL,
    "operational_score": Dimension.OPERATIONAL,
    "compliance_score": Dimension.COMPLIANCE,
    "geo_score": Dimension.GEOPOLITICAL,
    "esg_score": Dimension.ESG,
}

ALERT_THRESHOLD_HIGH = 65.0
ALERT_THRESHOLD_CRITICAL = 80.0


def _compute_stats(suppliers: dict) -> dict:
    """Compute portfolio-level stats from the supplier dict."""
    supplier_list = list(suppliers.values())
    total = len(supplier_list)
    if total == 0:
        return {"total": 0, "critical_count": 0, "high_count": 0,
                "avg_overall_score": 0.0, "unacknowledged_alert_count": 0}

    # Aggregate alerts from all suppliers
    total_alerts = []
    for s in supplier_list:
        total_alerts.extend(s.alerts)

    critical_count = sum(1 for s in supplier_list if s.risk_level == RiskLevel.CRITICAL)
    high_count = sum(1 for s in supplier_list if s.risk_level == RiskLevel.HIGH)
    avg_score = round(sum(s.overall_score for s in supplier_list) / total, 1)
    unacked = sum(1 for a in total_alerts if not a.acknowledged)

    return {
        "total": total,
        "critical_count": critical_count,
        "high_count": high_count,
        "avg_overall_score": avg_score,
        "unacknowledged_alert_count": unacked,
    }


async def run_scanner(
    suppliers: dict,
    alerts: list,
    alert_engine: "AlertEngine | None",
    ws_manager: "WSManager",
    stop_event: asyncio.Event,
) -> None:
    """Background task that continuously monitors and updates supplier risks.

    Runs until stop_event is set. Pushes all updates via WebSocket.
    """
    logger.info("Risk scanner started (interval=%ss)", SCAN_INTERVAL_SECONDS)

    while not stop_event.is_set():
        try:
            await _scan_cycle(suppliers, alerts, alert_engine, ws_manager)
        except Exception as e:
            logger.error(f"Scanner cycle error: {e}")

        # Wait for next cycle or stop signal
        try:
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            break


async def _scan_cycle(
    suppliers: dict,
    alerts: list,
    alert_engine: "AlertEngine | None",
    ws_manager: "WSManager",
) -> None:
    """Execute one scan cycle: tweak scores → check thresholds → broadcast."""
    if not suppliers:
        return

    # Pick multiple suppliers to scan per cycle for more visible activity
    all_supplier_ids = list(suppliers.keys())
    num_to_scan = min(SUPPLIERS_PER_CYCLE, len(all_supplier_ids))
    supplier_ids_to_scan = random.sample(all_supplier_ids, num_to_scan)

    for supplier_id in supplier_ids_to_scan:
        supplier = suppliers[supplier_id]

        # Pick multiple dimensions to tweak for more alert chances
        num_dims = random.randint(2, DIMS_PER_SUPPLIER)
        dims_to_tweak = random.sample(DIMENSION_KEYS, num_dims)

        triggered_alerts = []

        for dim_key in dims_to_tweak:
            # Apply a random delta to the dimension score
            delta = random.uniform(*SCORE_DELTA_RANGE)
            current = getattr(supplier, dim_key)
            new_score = max(0.0, min(100.0, current + delta))
            setattr(supplier, dim_key, round(new_score, 1))

            # Check if this dimension now crosses a threshold
            if new_score >= ALERT_THRESHOLD_CRITICAL:
                dimension = DIMENSION_MAP[dim_key]
                triggered_alerts.append((dimension, Severity.CRITICAL, new_score))
            elif new_score >= ALERT_THRESHOLD_HIGH:
                dimension = DIMENSION_MAP[dim_key]
                triggered_alerts.append((dimension, Severity.HIGH, new_score))

        # Recompute overall score
        old_level = supplier.risk_level
        supplier.overall_score = compute_overall_score(
            supplier.financial_score,
            supplier.operational_score,
            supplier.compliance_score,
            supplier.geo_score,
            supplier.esg_score,
        )

        # Update risk level and trend
        supplier.risk_level = determine_risk_level(supplier.overall_score)
        supplier.last_scanned_at = datetime.now(timezone.utc)

        # Update history (append new score, keep last 30)
        supplier.history.append(supplier.overall_score)
        if len(supplier.history) > 30:
            supplier.history = supplier.history[-30:]
        supplier.trend = determine_trend(supplier.history)

        # Track alert count for the supplier
        existing_alert_ids = {a.dimension: a for a in supplier.alerts if not a.acknowledged}

        # Generate LLM-powered alerts for any newly triggered dimensions
        for dimension, severity, dim_score in triggered_alerts:
            # Skip if there's already an unacknowledged alert for this dimension
            if dimension in existing_alert_ids:
                continue

            # Generate content via OpenRouter (or fallback)
            ai_model = ""
            if alert_engine:
                try:
                    result = await alert_engine.generate_alert_content(
                        supplier_name=supplier.name,
                        dimension=dimension.value,
                        score=dim_score,
                        severity=severity.value,
                        overall_score=supplier.overall_score,
                    )
                    ai_model = result.pop("ai_model", "")
                    title = result.get("title", f"{dimension.value.capitalize()} Risk Alert")
                    message = result.get("message", f"{supplier.name} triggered a {severity.value.lower()} alert in {dimension.value}.")
                    recommendations = result.get("recommendations", [
                        f"Review {dimension.value.lower()} metrics.",
                        f"Discuss mitigation with {supplier.name}.",
                        "Monitor closely over next 30 days.",
                    ])
                except Exception as e:
                    logger.error(f"OpenRouter alert generation failed: {e}")
                    title = f"{dimension.value.capitalize()} Risk: {severity.value} Level ({dim_score:.0f})"
                    message = f"{supplier.name} has triggered a {severity.value.lower()} risk alert in the {dimension.value.lower()} dimension."
                    recommendations = [
                        f"Review {dimension.value.lower()} metrics.",
                        f"Develop a mitigation plan.",
                        f"Schedule a review meeting with {supplier.name}.",
                    ]
            else:
                title = f"{dimension.value.capitalize()} Risk: {severity.value} Level ({dim_score:.0f})"
                message = f"{supplier.name} has triggered a {severity.value.lower()} risk alert in the {dimension.value.lower()} dimension."
                recommendations = [
                    f"Review {dimension.value.lower()} metrics.",
                    f"Develop a mitigation plan.",
                    f"Schedule a review meeting with {supplier.name}.",
                ]

            new_alert = Alert(
                alert_id=str(uuid.uuid4()),
                supplier_id=supplier.supplier_id,
                supplier_name=supplier.name,
                dimension=dimension,
                severity=severity,
                title=title,
                message=message,
                recommendations=recommendations,
            )

            # Add to supplier and global alerts
            supplier.alerts.append(new_alert)
            alerts.append(new_alert)

            logger.info(
                f"🔔 New alert: {supplier.name} — {dimension.value} "
                f"({severity.value}, score={dim_score:.1f})"
            )

            # Broadcast the new alert via WebSocket
            await ws_manager.broadcast("new_alert", {
                "alert": new_alert.model_dump(),
                "ai_model": ai_model or "fallback",
            })

        # Broadcast score update for EACH supplier
        await ws_manager.broadcast("score_update", {
            "supplier_id": supplier.supplier_id,
            "name": supplier.name,
            "country": supplier.country,
            "industry": supplier.industry,
            "financial_score": supplier.financial_score,
            "operational_score": supplier.operational_score,
            "compliance_score": supplier.compliance_score,
            "geo_score": supplier.geo_score,
            "esg_score": supplier.esg_score,
            "overall_score": supplier.overall_score,
            "risk_level": supplier.risk_level.value,
            "trend": supplier.trend.value,
            "alert_count": len(supplier.alerts),
        })

    # Broadcast stats update ONCE per cycle (after all suppliers processed)
    stats = _compute_stats(suppliers)
    await ws_manager.broadcast("stats_update", stats)
