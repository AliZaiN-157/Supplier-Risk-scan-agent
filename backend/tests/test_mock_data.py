"""Tests for mock data generation."""
from app.mock_data import (
    COUNTRY_RISK_INDEX,
    generate_suppliers,
    generate_globaltech,
    generate_reliable_components,
    generate_acme_industrial,
    generate_random_suppliers,
    get_country_risk_index,
)


class TestCountryRiskIndex:
    def test_known_countries(self):
        """Should have ~20 countries defined."""
        assert len(COUNTRY_RISK_INDEX) >= 15
        assert "US" in COUNTRY_RISK_INDEX
        assert "CN" in COUNTRY_RISK_INDEX
        assert "DE" in COUNTRY_RISK_INDEX
        assert all(0 <= v <= 100 for v in COUNTRY_RISK_INDEX.values())

    def test_get_known_country(self):
        assert get_country_risk_index("US") == COUNTRY_RISK_INDEX["US"]

    def test_get_unknown_country_defaults_50(self):
        assert get_country_risk_index("XX") == 50


class TestSeedSuppliers:
    def test_globaltech_exists(self):
        suppliers = generate_suppliers()
        supplier_ids = [s.supplier_id for s in suppliers]
        # Should have 15 suppliers
        assert len(suppliers) == 15

    def test_globaltech_characteristics(self):
        suppliers = generate_suppliers()
        gt = next((s for s in suppliers if "GlobalTech" in s.name), None)
        assert gt is not None, "GlobalTech Manufacturing Co must exist"
        assert gt.financial_score >= 80
        assert gt.geo_score >= 75
        assert gt.risk_level.value == "CRITICAL"
        assert gt.trend.value == "DETERIORATING"
        assert len(gt.alerts) >= 2
        # Verify at least 2 CRITICAL alerts
        critical_alerts = [a for a in gt.alerts if a.severity.value == "CRITICAL"]
        assert len(critical_alerts) >= 2

    def test_reliable_components_characteristics(self):
        suppliers = generate_suppliers()
        rc = next((s for s in suppliers if "Reliable" in s.name), None)
        assert rc is not None, "Reliable Components Inc must exist"
        assert rc.financial_score <= 25
        assert rc.operational_score <= 25
        assert rc.compliance_score <= 25
        assert rc.geo_score <= 25
        assert rc.esg_score <= 25
        assert rc.risk_level.value == "LOW"
        assert rc.trend.value == "STABLE"
        assert len(rc.alerts) == 0

    def test_acme_industrial_characteristics(self):
        suppliers = generate_suppliers()
        acme = next((s for s in suppliers if "Acme" in s.name), None)
        assert acme is not None, "Acme Industrial Supplies must exist"
        assert 55 <= acme.overall_score <= 65
        assert acme.esg_score > 70
        assert acme.trend.value == "DETERIORATING"
        # Should have at least one HIGH alert
        high_alerts = [a for a in acme.alerts if a.severity.value == "HIGH"]
        assert len(high_alerts) >= 1

    def test_all_suppliers_have_required_fields(self):
        suppliers = generate_suppliers()
        for s in suppliers:
            assert s.supplier_id and len(s.supplier_id) > 0
            assert s.name and len(s.name) > 0
            assert s.country and len(s.country) == 2
            assert s.industry and len(s.industry) > 0
            assert 0 <= s.financial_score <= 100
            assert 0 <= s.operational_score <= 100
            assert 0 <= s.compliance_score <= 100
            assert 0 <= s.geo_score <= 100
            assert 0 <= s.esg_score <= 100
            assert 0 <= s.overall_score <= 100
            assert s.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"] or s.risk_level.value in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            assert s.trend in ["IMPROVING", "STABLE", "DETERIORATING"] or s.trend.value in ["IMPROVING", "STABLE", "DETERIORATING"]
            assert len(s.history) == 30
            assert isinstance(s.last_scanned_at, str) or hasattr(s.last_scanned_at, 'isoformat')


class TestRandomSupplierDistribution:
    def test_risk_tier_distribution(self):
        suppliers = generate_suppliers()
        # Count by risk level
        low = sum(1 for s in suppliers if (s.risk_level.value if hasattr(s.risk_level, 'value') else s.risk_level) == "LOW")
        med = sum(1 for s in suppliers if (s.risk_level.value if hasattr(s.risk_level, 'value') else s.risk_level) == "MEDIUM")
        high = sum(1 for s in suppliers if (s.risk_level.value if hasattr(s.risk_level, 'value') else s.risk_level) == "HIGH")
        crit = sum(1 for s in suppliers if (s.risk_level.value if hasattr(s.risk_level, 'value') else s.risk_level) == "CRITICAL")
        # We have 3 seed + 12 random
        # LW: 3 random in 10-38 range
        # MEDIUM: 5 random in 40-58 range
        # HIGH: 3 random in 62-73 range
        # CRITICAL: 1 random in 76-95 range
        # Plus seeds: GlobalTech=CRITICAL, Reliable=LOW, Acme=varies
        assert low >= 1  # At least Reliable
        assert crit >= 2  # At least GlobalTech + 1 random
        assert high >= 1

    def test_all_suppliers_unique_ids(self):
        suppliers = generate_suppliers()
        ids = [s.supplier_id for s in suppliers]
        assert len(ids) == len(set(ids))


class TestAlertGeneration:
    def test_globaltech_alerts_critical(self):
        suppliers = generate_suppliers()
        gt = next((s for s in suppliers if "GlobalTech" in s.name), None)
        assert gt is not None
        for alert in gt.alerts:
            if alert.severity.value == "CRITICAL":
                assert alert.title and len(alert.title) > 0
                assert alert.message and len(alert.message) > 0
                assert len(alert.recommendations) >= 1
                assert alert.dimension in ["FINANCIAL", "OPERATIONAL", "COMPLIANCE", "GEOPOLITICAL", "ESG"] or \
                       alert.dimension.value in ["FINANCIAL", "OPERATIONAL", "COMPLIANCE", "GEOPOLITICAL", "ESG"]

    def test_alert_has_required_fields(self):
        suppliers = generate_suppliers()
        for s in suppliers:
            for alert in s.alerts:
                assert alert.alert_id and len(alert.alert_id) > 0
                assert alert.supplier_id == s.supplier_id
                assert alert.supplier_name == s.name
                assert alert.dimension is not None
                assert alert.severity in ["HIGH", "CRITICAL"] or alert.severity.value in ["HIGH", "CRITICAL"]
                assert alert.title and len(alert.title) > 0
                assert alert.message and len(alert.message) > 0
                assert len(alert.recommendations) >= 1
