"""FastAPI route handlers per §4 of the PRD."""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query, Request
from app.models import (
    Supplier, Alert, Stats, BulkAcknowledgeRequest,
    Severity, RiskLevel,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_store(request: Request) -> dict:
    """Access the in-memory store from app state."""
    return {
        "suppliers": request.app.state.suppliers,
        "alerts": request.app.state.alerts,
    }


@router.get("/suppliers", response_model=list[Supplier])
async def get_suppliers(request: Request):
    """
    GET /suppliers — Return all 15 suppliers with current scores,
    risk level, trend, and active alerts.

    Per §4 API spec — no parameters, returns Array<Supplier>.
    """
    store = _get_store(request)
    return list(store["suppliers"].values())


@router.get("/suppliers/{supplier_id}", response_model=Supplier)
async def get_supplier(request: Request, supplier_id: str):
    """
    GET /suppliers/{id} — Return a single supplier including 30-day score history.

    Returns 404 if supplier_id not found.
    """
    store = _get_store(request)
    supplier = store["suppliers"].get(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.get("/alerts", response_model=list[Alert])
async def get_alerts(
    request: Request,
    severity: Severity | None = Query(None, description="Filter by severity: HIGH or CRITICAL"),
    acknowledged: bool | None = Query(None, description="Filter by acknowledged status"),
    supplier_id: str | None = Query(None, description="Filter by supplier ID"),
):
    """
    GET /alerts — Return all alerts with optional query filters.

    Supports: ?severity=HIGH|CRITICAL, ?acknowledged=true|false,
    ?supplier_id=uuid
    """
    store = _get_store(request)
    alerts = store["alerts"]

    if severity:
        alerts = [a for a in alerts if a.severity == severity]

    if acknowledged is not None:
        alerts = [a for a in alerts if a.acknowledged == acknowledged]

    if supplier_id:
        alerts = [a for a in alerts if a.supplier_id == supplier_id]

    return alerts


@router.patch("/alerts/{alert_id}/acknowledge", response_model=Alert)
async def acknowledge_alert(request: Request, alert_id: str):
    """
    PATCH /alerts/{id}/acknowledge — Mark a single alert as acknowledged.

    Returns 404 if alert not found.
    """
    store = _get_store(request)
    for alert in store["alerts"]:
        if alert.alert_id == alert_id:
            alert.acknowledged = True
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")


@router.post("/alerts/bulk-acknowledge")
async def bulk_acknowledge_alerts(
    request: Request,
    body: BulkAcknowledgeRequest,
):
    """
    POST /alerts/bulk-acknowledge — Acknowledge multiple alerts in one request.

    Body: { alert_ids: string[] }
    Returns: { acknowledged_count: number }
    """
    store = _get_store(request)
    count = 0
    for alert in store["alerts"]:
        if alert.alert_id in body.alert_ids:
            alert.acknowledged = True
            count += 1
    return {"acknowledged_count": count}


@router.get("/stats", response_model=Stats)
async def get_stats(request: Request):
    """
    GET /stats — Return portfolio-level aggregates for dashboard overview cards.

    Returns: { total, critical_count, high_count, avg_overall_score,
    unacknowledged_alert_count }
    """
    store = _get_store(request)
    suppliers = list(store["suppliers"].values())
    alerts = store["alerts"]

    total = len(suppliers)
    critical_count = sum(
        1 for s in suppliers if s.risk_level == RiskLevel.CRITICAL
    )
    high_count = sum(
        1 for s in suppliers if s.risk_level == RiskLevel.HIGH
    )
    avg_overall_score = (
        round(sum(s.overall_score for s in suppliers) / total, 1)
        if total > 0
        else 0.0
    )
    unacknowledged_alert_count = sum(
        1 for a in alerts if not a.acknowledged
    )

    return Stats(
        total=total,
        critical_count=critical_count,
        high_count=high_count,
        avg_overall_score=avg_overall_score,
        unacknowledged_alert_count=unacknowledged_alert_count,
    )
