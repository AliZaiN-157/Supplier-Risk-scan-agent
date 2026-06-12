# Design Document: Supplier Risk Scan Agent

## Why This Exists

Procurement teams work with many suppliers at the same time. Problems like a supplier going into financial trouble, getting hit with trade sanctions, or failing compliance audits often go unnoticed until they cause real damage. This system automates the monitoring. It watches supplier data, spots when something crosses a danger line, and writes a clear alert about what happened and what to do about it.

## Architecture Overview

The system has two parts: a Python backend that holds data and runs calculations, and a React frontend that shows the data on screen. They communicate through a REST API and a WebSocket connection.

```
Browser (React)  <--HTTP-->  Nginx  <--HTTP/WS-->  FastAPI Backend
                                       |
                                  [Background Scanner]
                                       |
                                  [OpenRouter AI]
```

The frontend is served through Nginx in production. Nginx handles routing for the single-page application and proxies API and WebSocket calls to the backend. In development, Vite's dev server handles the proxying instead.

## Backend

The backend is a FastAPI application. Everything runs in a single process. There is no database. All data lives in Python dictionaries in memory and resets when the application restarts.

### Startup Sequence

When the application starts:

1. The mock data generator creates 15 suppliers with scores, histories, and initial alerts.
2. The suppliers go into a dict keyed by supplier ID. Alerts go into a flat list.
3. The alert engine initializes with the OpenRouter API key (if one was provided in the .env file).
4. A background task starts running the scanner loop.

### Risk Scoring

Each supplier has five dimension scores. Each score is calculated from raw business metrics using deterministic formulas. There is no randomness in the scoring itself. The formulas are in `risk_scorer.py`.

For example, the financial score looks at credit score (inverted, since higher credit means lower risk), profit margin (negative margin adds a penalty), days sales outstanding (slow payment adds a penalty), and debt ratio. Each component gets a weight, and penalties stack on top.

The overall score is a weighted average of the five dimensions. The weights are fixed: financial 30%, operational 25%, compliance 20%, geopolitical 15%, ESG 10%.

### Alert Generation

When a dimension score crosses 65 (HIGH) or 80 (CRITICAL), the scanner flags it. If there is no unacknowledged alert already for that supplier and dimension, it calls the alert engine.

The alert engine sends a prompt to OpenRouter asking for:
- A short headline (under 12 words)
- A two-sentence explanation of what is happening and why it matters
- Three recommended actions

The AI must return valid JSON. If the API call fails or no key is configured, the system uses pre-written fallback text. This means the app works without any API key.

### Background Scanner

The scanner runs every 8 seconds. Each cycle:
1. Picks 3 random suppliers.
2. For each supplier, tweaks 2 to 3 dimension scores by a random amount between -12 and +12.
3. Recalculates the overall score, risk level, and trend.
4. Checks if any dimension crossed a threshold.
5. For each new threshold crossing, generates an alert (via OpenRouter or fallback).
6. Broadcasts score updates and any new alerts to all WebSocket clients.
7. Broadcasts updated portfolio stats once per cycle.

### WebSocket

The WebSocket endpoint at /ws uses a connection manager that keeps track of all active clients. When the scanner produces an update, the manager broadcasts it as a JSON message to every connected client. Dead connections get cleaned up automatically.

Three event types are pushed:
- score_update -- one supplier's scores changed
- new_alert -- a new alert was created
- stats_update -- portfolio-level numbers changed

## Frontend

The frontend is a React single-page application built with Vite and TypeScript. It uses Recharts for charts and Tailwind for styling.

### Pages

**Landing Page** (`/`): A marketing-style landing page with feature highlights and links to the dashboard and suppliers page.

**Dashboard** (`/dashboard`): The main view. Shows five KPI cards (total suppliers, average risk score, critical count, high count, unacknowledged alerts), two bar charts (risk distribution by level, top 10 highest-risk suppliers), a table of the top 5 high-risk suppliers, and a feed of the 10 most recent alerts. Connects to the WebSocket on mount and updates in real time. Also has an Export PDF button that generates a landscape print layout.

**Suppliers** (`/suppliers`): A searchable, sortable list of all 15 suppliers. Each card shows the overall score, risk level, country, industry, trend, and mini dimension bars.

**Supplier Detail** (`/suppliers/:id`): Shows a single supplier with an SVG score gauge, a five-axis radar chart of dimension scores, a 30-day history line chart with threshold reference lines, dimension score bars, and a list of active alerts with recommendation details.

**Alerts Center** (`/alerts`): A filterable table of all alerts. Filters for severity (ALL, CRITICAL, HIGH), status (ALL, OPEN, ACKNOWLEDGED), and dimension (ALL, FINANCIAL, OPERATIONAL, COMPLIANCE, GEOPOLITICAL, ESG). Supports individual acknowledgment and bulk acknowledgment with checkboxes. Connects to WebSocket to receive new alerts in real time.

### Data Flow

On page load, the frontend fetches initial data from the REST API. Then it opens a WebSocket connection. From that point on, all updates come through the WebSocket. There is no polling. If the WebSocket disconnects, the client attempts to reconnect with exponential backoff starting at 2 seconds and maxing at 30 seconds.

The API calls go through `/api/*` which gets proxied to the backend. The WebSocket connects to `/ws` on the same host.

## Data Model

### Supplier

| Field | Type | Notes |
|---|---|---|
| supplier_id | UUID | Primary key |
| name | string | Company name |
| country | string | ISO 3166-1 alpha-2 code |
| industry | string | Manufacturing, Electronics, etc. |
| financial_score | float | 0 to 100 |
| operational_score | float | 0 to 100 |
| compliance_score | float | 0 to 100 |
| geo_score | float | 0 to 100 |
| esg_score | float | 0 to 100 |
| overall_score | float | Weighted average of dimensions |
| risk_level | enum | LOW, MEDIUM, HIGH, CRITICAL |
| trend | enum | IMPROVING, STABLE, DETERIORATING |
| history | float[] | 30 daily overall score snapshots |
| alerts | Alert[] | Active alerts for this supplier |
| last_scanned_at | datetime | Last scanner run timestamp |

### Alert

| Field | Type | Notes |
|---|---|---|
| alert_id | UUID | Primary key |
| supplier_id | UUID | Foreign key to supplier |
| supplier_name | string | Denormalized for convenience |
| dimension | enum | FINANCIAL, OPERATIONAL, COMPLIANCE, GEOPOLITICAL, ESG |
| severity | enum | HIGH, CRITICAL |
| title | string | Short headline |
| message | string | Two-sentence explanation |
| recommendations | string[] | Three mitigation steps |
| acknowledged | bool | Default false |
| created_at | datetime | ISO-8601 timestamp |

## Docker Setup

Two containers are defined in docker-compose.yml:

**Backend container**: Built from a two-stage Dockerfile. The builder stage uses an official Python 3.12 slim image and installs dependencies with uv (the fast Python package manager). The runtime stage is a fresh Python 3.12 slim image that only contains the virtual environment and the application code. It runs as a non-root user. A healthcheck hits the /stats endpoint every 10 seconds after a 15-second startup grace period.

**Frontend container**: Built from a two-stage Dockerfile. The builder stage uses a Node 22 alpine image to compile the TypeScript and bundle with Vite. The runtime stage is an Nginx 1.27 alpine image that serves the built files. The Nginx config handles SPA routing (all unknown paths serve index.html), proxies /api calls to the backend (stripping the /api prefix), and proxies /ws with WebSocket upgrade headers. The frontend waits for the backend healthcheck to pass before starting.

## Mock Data Distribution

The system creates 15 suppliers:

- 3 seed suppliers with fixed names and characteristics
- 2 edge suppliers with scores just below alert thresholds (for demo purposes)
- 10 randomly generated suppliers spread across risk tiers

The seed suppliers match the requirements from the assessment specification:
- GlobalTech Manufacturing Co: critical, deteriorating, Chinese manufacturing company
- Reliable Components Inc: low, stable, German electronics company
- Acme Industrial Supplies: medium-to-high, deteriorating, Indian manufacturing company

## Testing

The backend has 106 tests covering:
- Risk scorer functions (dimension scores, overall score, risk level, trend)
- Alert engine (threshold detection, prompt generation, response parsing)
- Mock data generation (structure and content of generated suppliers)
- API routes (all endpoints with various parameters)
- Data models (validation, serialization)

The frontend does not have tests yet.

Nginx is the production-grade gateway that serves your React app, handles SPA routing, proxies API calls to the backend, and keeps WebSocket connections alive for real-time alerts — all from a single origin so you don't need CORS workarounds
