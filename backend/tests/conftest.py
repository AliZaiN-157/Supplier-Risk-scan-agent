"""Pytest fixtures and configuration."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.mock_data import generate_suppliers


@pytest.fixture
def test_suppliers():
    """Generate 15 suppliers for testing."""
    return generate_suppliers()


@pytest.fixture
def app(test_suppliers):
    """Create FastAPI app with pre-loaded suppliers."""
    application = create_app()
    # Override the in-memory store
    application.state.suppliers = {s.supplier_id: s for s in test_suppliers}
    # Collect all alerts
    all_alerts = []
    for s in test_suppliers:
        for alert in s.alerts:
            all_alerts.append(alert)
    application.state.alerts = all_alerts
    return application


@pytest.fixture
async def client(app):
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
