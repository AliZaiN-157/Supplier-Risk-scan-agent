"""Pydantic data models matching §2.1 and §2.2 of the PRD."""
from __future__ import annotations
from enum import Enum
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Trend(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DETERIORATING = "DETERIORATING"


class Severity(str, Enum):
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Dimension(str, Enum):
    FINANCIAL = "FINANCIAL"
    OPERATIONAL = "OPERATIONAL"
    COMPLIANCE = "COMPLIANCE"
    GEOPOLITICAL = "GEOPOLITICAL"
    ESG = "ESG"


class Alert(BaseModel):
    """Alert object per §2.2 of the PRD."""
    alert_id: str
    supplier_id: str
    supplier_name: str
    dimension: Dimension
    severity: Severity
    title: str = Field(..., max_length=120)
    message: str
    recommendations: list[str]
    acknowledged: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Supplier(BaseModel):
    """Supplier object per §2.1 of the PRD."""
    supplier_id: str
    name: str
    country: str = Field(..., min_length=2, max_length=2)
    industry: str
    financial_score: float = Field(..., ge=0, le=100)
    operational_score: float = Field(..., ge=0, le=100)
    compliance_score: float = Field(..., ge=0, le=100)
    geo_score: float = Field(..., ge=0, le=100)
    esg_score: float = Field(..., ge=0, le=100)
    overall_score: float = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    trend: Trend
    history: list[float] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    last_scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Stats(BaseModel):
    """Portfolio-level aggregates for dashboard overview."""
    total: int
    critical_count: int
    high_count: int
    avg_overall_score: float
    unacknowledged_alert_count: int


class SupplierCreate(BaseModel):
    """Schema for creating a new supplier (for future use)."""
    name: str
    country: str = Field(..., min_length=2, max_length=2)
    industry: str


class AlertCreate(BaseModel):
    """Schema for manually creating an alert (for future use)."""
    supplier_id: str
    dimension: Dimension
    severity: Severity
    title: str
    message: str
    recommendations: list[str]


class BulkAcknowledgeRequest(BaseModel):
    """Request body for bulk acknowledge endpoint."""
    alert_ids: list[str]
