"""Tests for data models."""
from app.models import (
    RiskLevel, Trend, Severity, Dimension,
    Alert, Supplier, Stats, SupplierCreate, AlertCreate
)
from datetime import datetime, timezone


def test_risk_level_enum_values():
    assert RiskLevel.LOW.value == "LOW"
    assert RiskLevel.MEDIUM.value == "MEDIUM"
    assert RiskLevel.HIGH.value == "HIGH"
    assert RiskLevel.CRITICAL.value == "CRITICAL"


def test_trend_enum_values():
    assert Trend.IMPROVING.value == "IMPROVING"
    assert Trend.STABLE.value == "STABLE"
    assert Trend.DETERIORATING.value == "DETERIORATING"


def test_severity_enum_values():
    assert Severity.HIGH.value == "HIGH"
    assert Severity.CRITICAL.value == "CRITICAL"


def test_dimension_enum_values():
    assert Dimension.FINANCIAL.value == "FINANCIAL"
    assert Dimension.OPERATIONAL.value == "OPERATIONAL"
    assert Dimension.COMPLIANCE.value == "COMPLIANCE"
    assert Dimension.GEOPOLITICAL.value == "GEOPOLITICAL"
    assert Dimension.ESG.value == "ESG"


def test_supplier_model_defaults():
    supplier = Supplier(
        supplier_id="uuid-123",
        name="Test Corp",
        country="US",
        industry="Manufacturing",
        financial_score=50.0,
        operational_score=50.0,
        compliance_score=50.0,
        geo_score=50.0,
        esg_score=50.0,
        overall_score=50.0,
        risk_level=RiskLevel.MEDIUM,
        trend=Trend.STABLE,
    )
    assert supplier.supplier_id == "uuid-123"
    assert supplier.name == "Test Corp"
    assert supplier.country == "US"
    assert supplier.industry == "Manufacturing"
    assert supplier.financial_score == 50.0
    assert supplier.risk_level == RiskLevel.MEDIUM
    assert supplier.trend == Trend.STABLE
    assert supplier.history == []
    assert supplier.alerts == []
    assert isinstance(supplier.last_scanned_at, datetime)


def test_supplier_model_with_history_and_alerts():
    alert = Alert(
        alert_id="alert-1",
        supplier_id="sup-1",
        supplier_name="Test Corp",
        dimension=Dimension.FINANCIAL,
        severity=Severity.HIGH,
        title="High financial risk",
        message="Financial risk detected.",
        recommendations=["Reduce debt", "Improve margin"],
    )
    now = datetime.now(timezone.utc)
    supplier = Supplier(
        supplier_id="sup-1",
        name="Test Corp",
        country="US",
        industry="Manufacturing",
        financial_score=80.0,
        operational_score=50.0,
        compliance_score=50.0,
        geo_score=50.0,
        esg_score=50.0,
        overall_score=62.0,
        risk_level=RiskLevel.HIGH,
        trend=Trend.DETERIORATING,
        history=[50.0, 55.0, 62.0],
        alerts=[alert],
        last_scanned_at=now,
    )
    assert len(supplier.history) == 3
    assert len(supplier.alerts) == 1
    assert supplier.alerts[0].dimension == Dimension.FINANCIAL
    assert supplier.alerts[0].severity == Severity.HIGH
    assert supplier.alerts[0].acknowledged is False
    assert supplier.last_scanned_at == now


def test_alert_model():
    alert = Alert(
        alert_id="alert-1",
        supplier_id="sup-1",
        supplier_name="Test Corp",
        dimension=Dimension.COMPLIANCE,
        severity=Severity.CRITICAL,
        title="Compliance breach",
        message="ISO cert expiring soon.",
        recommendations=["Renew cert", "Audit processes"],
    )
    assert alert.alert_id == "alert-1"
    assert alert.supplier_id == "sup-1"
    assert alert.dimension == Dimension.COMPLIANCE
    assert alert.severity == Severity.CRITICAL
    assert alert.title == "Compliance breach"
    assert len(alert.recommendations) == 2
    assert alert.acknowledged is False
    assert isinstance(alert.created_at, datetime)


def test_alert_acknowledge():
    alert = Alert(
        alert_id="alert-1",
        supplier_id="sup-1",
        supplier_name="Test Corp",
        dimension=Dimension.ESG,
        severity=Severity.HIGH,
        title="ESG concern",
        message="Environmental score dropped.",
        recommendations=["Improve practices"],
    )
    assert alert.acknowledged is False
    # Simulate acknowledge
    alert.acknowledged = True
    assert alert.acknowledged is True


def test_stats_model():
    stats = Stats(
        total=15,
        critical_count=3,
        high_count=4,
        avg_overall_score=42.5,
        unacknowledged_alert_count=7,
    )
    assert stats.total == 15
    assert stats.critical_count == 3
    assert stats.high_count == 4
    assert stats.avg_overall_score == 42.5
    assert stats.unacknowledged_alert_count == 7


def test_supplier_create_model():
    sc = SupplierCreate(
        name="New Supplier",
        country="DE",
        industry="Electronics",
    )
    assert sc.name == "New Supplier"
    assert sc.country == "DE"
    assert sc.industry == "Electronics"


def test_alert_create_model():
    ac = AlertCreate(
        supplier_id="sup-1",
        dimension=Dimension.FINANCIAL,
        severity=Severity.HIGH,
        title="Test Alert",
        message="Alert message body",
        recommendations=["Rec 1", "Rec 2", "Rec 3"],
    )
    assert ac.supplier_id == "sup-1"
    assert len(ac.recommendations) == 3
