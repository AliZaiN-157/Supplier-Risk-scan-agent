"""FastAPI application entrypoint per §4 of the PRD.

Creates the app, initialises in-memory store with 15 suppliers on startup,
registers all routes, starts the background risk scanner, and exposes a
WebSocket endpoint for real-time dashboard updates.
"""
from __future__ import annotations
import asyncio
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.routes import router
from app.mock_data import generate_suppliers
from app.alert_engine import AlertEngine
from app.ws_manager import WSManager
from app.scanner import run_scanner

# Load .env file from the backend directory
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Factory to create and configure the FastAPI application."""

    ws_manager = WSManager()
    stop_scanner = asyncio.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Startup: generate mock data, initialise alert engine, start scanner."""
        logger.info("Generating 15 mock suppliers...")
        suppliers_list = generate_suppliers()
        app.state.suppliers = {s.supplier_id: s for s in suppliers_list}

        # Collect all alerts from suppliers into a flat list
        all_alerts = []
        for s in suppliers_list:
            for alert in s.alerts:
                all_alerts.append(alert)
        app.state.alerts = all_alerts

        # Initialise alert engine with optional OpenRouter API key
        api_key = os.environ.get("OPENROUTER_API_KEY")
        alert_engine = AlertEngine(api_key=api_key)
        app.state.alert_engine = alert_engine
        app.state.ws_manager = ws_manager

        logger.info(
            f"Startup complete: {len(suppliers_list)} suppliers, "
            f"{len(all_alerts)} alerts generated."
        )

        # Start background risk scanner
        scanner_task = asyncio.create_task(
            run_scanner(
                suppliers=app.state.suppliers,
                alerts=app.state.alerts,
                alert_engine=alert_engine,
                ws_manager=ws_manager,
                stop_event=stop_scanner,
            )
        )

        yield  # Application runs here

        # Shutdown: stop scanner and clean up
        stop_scanner.set()
        scanner_task.cancel()
        try:
            await scanner_task
        except asyncio.CancelledError:
            pass
        logger.info("Scanner stopped — application shutting down.")

    application = FastAPI(
        title="Supplier Risk Scan Agent",
        description="Autonomous system that evaluates supplier health "
                    "across five risk dimensions and fires intelligent alerts.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(router)
    application.state.ws_manager = ws_manager

    @application.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time dashboard updates.

        Clients connect here to receive live events:
          - score_update:   a supplier's dimension/overall scores changed
          - new_alert:      a new AI-generated alert was created
          - stats_update:   portfolio-level aggregate stats changed

        The server sends these events automatically via the background scanner.
        The client can also send a 'ping' message to keep the connection alive.
        """
        await ws_manager.connect(websocket)
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    if data.strip().lower() == "ping":
                        await websocket.send_text('{"type":"pong"}')
                except WebSocketDisconnect:
                    break
        except Exception:
            pass
        finally:
            ws_manager.disconnect(websocket)

    return application


app = create_app()
