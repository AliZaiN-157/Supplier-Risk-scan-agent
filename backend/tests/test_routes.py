"""Tests for API routes."""
import pytest


class TestGetSuppliers:
    async def test_returns_all_suppliers(self, client):
        response = await client.get("/suppliers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 15

    async def test_supplier_shape(self, client):
        response = await client.get("/suppliers")
        data = response.json()[0]
        assert "supplier_id" in data
        assert "name" in data
        assert "country" in data
        assert "industry" in data
        assert "financial_score" in data
        assert "operational_score" in data
        assert "compliance_score" in data
        assert "geo_score" in data
        assert "esg_score" in data
        assert "overall_score" in data
        assert "risk_level" in data
        assert "trend" in data
        assert "history" in data
        assert "alerts" in data
        assert "last_scanned_at" in data

    async def test_globaltech_present(self, client):
        response = await client.get("/suppliers")
        data = response.json()
        names = [s["name"] for s in data]
        assert any("GlobalTech" in n for n in names)

    async def test_reliable_components_present(self, client):
        response = await client.get("/suppliers")
        data = response.json()
        names = [s["name"] for s in data]
        assert any("Reliable" in n for n in names)

    async def test_acme_industrial_present(self, client):
        response = await client.get("/suppliers")
        data = response.json()
        names = [s["name"] for s in data]
        assert any("Acme" in n for n in names)


class TestGetSupplierById:
    async def test_found(self, client):
        # Get all suppliers first to find an ID
        resp = await client.get("/suppliers")
        suppliers = resp.json()
        target_id = suppliers[0]["supplier_id"]

        response = await client.get(f"/suppliers/{target_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["supplier_id"] == target_id

    async def test_not_found(self, client):
        response = await client.get("/suppliers/nonexistent-id")
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_globaltech_critical(self, client):
        response = await client.get("/suppliers")
        data = response.json()
        gt = next(s for s in data if "GlobalTech" in s["name"])
        assert gt["risk_level"] == "CRITICAL"
        assert len(gt["alerts"]) >= 2

    async def test_reliable_low_risk(self, client):
        response = await client.get("/suppliers")
        data = response.json()
        rc = next(s for s in data if "Reliable" in s["name"])
        assert rc["risk_level"] == "LOW"
        assert len(rc["alerts"]) == 0


class TestGetAlerts:
    async def test_returns_all_alerts(self, client):
        response = await client.get("/alerts")
        assert response.status_code == 200
        data = response.json()
        # Should have alerts from high-risk suppliers
        assert len(data) >= 2  # At least GlobalTech alerts

    async def test_alert_shape(self, client):
        response = await client.get("/alerts")
        data = response.json()
        if len(data) > 0:
            alert = data[0]
            assert "alert_id" in alert
            assert "supplier_id" in alert
            assert "supplier_name" in alert
            assert "dimension" in alert
            assert "severity" in alert
            assert "title" in alert
            assert "message" in alert
            assert "recommendations" in alert
            assert "acknowledged" in alert
            assert "created_at" in alert

    async def test_filter_by_severity_high(self, client):
        response = await client.get("/alerts?severity=HIGH")
        assert response.status_code == 200
        data = response.json()
        for alert in data:
            assert alert["severity"] == "HIGH"

    async def test_filter_by_severity_critical(self, client):
        response = await client.get("/alerts?severity=CRITICAL")
        assert response.status_code == 200
        data = response.json()
        for alert in data:
            assert alert["severity"] == "CRITICAL"

    async def test_filter_by_acknowledged(self, client):
        response = await client.get("/alerts?acknowledged=false")
        assert response.status_code == 200
        data = response.json()
        for alert in data:
            assert alert["acknowledged"] is False

    async def test_filter_by_supplier_id(self, client):
        # Get a supplier ID
        resp = await client.get("/suppliers")
        suppliers = resp.json()
        target_sup = next(s for s in suppliers if len(s["alerts"]) > 0)
        sup_id = target_sup["supplier_id"]

        response = await client.get(f"/alerts?supplier_id={sup_id}")
        assert response.status_code == 200
        data = response.json()
        for alert in data:
            assert alert["supplier_id"] == sup_id

    async def test_invalid_severity_returns_400(self, client):
        response = await client.get("/alerts?severity=INVALID")
        assert response.status_code == 422  # FastAPI validation error


class TestAcknowledgeAlert:
    async def test_acknowledge_success(self, client):
        # Get an unacknowledged alert
        resp = await client.get("/alerts?acknowledged=false")
        alerts = resp.json()
        if len(alerts) > 0:
            target_alert = alerts[0]
            alert_id = target_alert["alert_id"]

            response = await client.patch(f"/alerts/{alert_id}/acknowledge")
            assert response.status_code == 200
            data = response.json()
            assert data["acknowledged"] is True
            assert data["alert_id"] == alert_id

    async def test_acknowledge_not_found(self, client):
        response = await client.patch("/alerts/nonexistent/acknowledge")
        assert response.status_code == 404

    async def test_acknowledge_changes_status(self, client):
        """After acknowledging, the alert should show as acknowledged."""
        resp = await client.get("/alerts?acknowledged=false")
        alerts = resp.json()
        if len(alerts) > 0:
            target_alert = alerts[0]
            alert_id = target_alert["alert_id"]

            await client.patch(f"/alerts/{alert_id}/acknowledge")

            # Verify it's now acknowledged
            verify = await client.get(f"/alerts?acknowledged=true")
            acked_ids = [a["alert_id"] for a in verify.json()]
            assert alert_id in acked_ids


class TestBulkAcknowledge:
    async def test_bulk_acknowledge_success(self, client):
        # Get unacknowledged alerts
        resp = await client.get("/alerts?acknowledged=false")
        alerts = resp.json()
        if len(alerts) >= 2:
            alert_ids = [a["alert_id"] for a in alerts[:2]]

            response = await client.post(
                "/alerts/bulk-acknowledge",
                json={"alert_ids": alert_ids}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["acknowledged_count"] == 2

    async def test_bulk_acknowledge_empty_list(self, client):
        response = await client.post(
            "/alerts/bulk-acknowledge",
            json={"alert_ids": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["acknowledged_count"] == 0

    async def test_bulk_partial_success(self, client):
        """Should acknowledge only valid IDs."""
        response = await client.post(
            "/alerts/bulk-acknowledge",
            json={"alert_ids": ["nonexistent-id-1", "nonexistent-id-2"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["acknowledged_count"] == 0


class TestGetStats:
    async def test_stats_shape(self, client):
        response = await client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "critical_count" in data
        assert "high_count" in data
        assert "avg_overall_score" in data
        assert "unacknowledged_alert_count" in data

    async def test_stats_values(self, client):
        response = await client.get("/stats")
        data = response.json()
        assert data["total"] == 15
        assert data["critical_count"] >= 1  # At least GlobalTech
        assert 0 <= data["avg_overall_score"] <= 100
        assert data["unacknowledged_alert_count"] >= 1

    async def test_stats_critical_count(self, client):
        response = await client.get("/suppliers")
        suppliers = response.json()
        expected_critical = sum(1 for s in suppliers if s["risk_level"] == "CRITICAL")

        stats_resp = await client.get("/stats")
        stats = stats_resp.json()
        assert stats["critical_count"] == expected_critical
