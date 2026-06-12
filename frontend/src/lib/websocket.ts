/**
 * WebSocket client for real-time dashboard updates.
 *
 * Connects to the backend WebSocket endpoint, automatically reconnects on
 * disconnect, and dispatches typed events to registered listeners.
 *
 * Events received:
 *   - score_update:  a supplier's scores changed
 *   - new_alert:     a new AI-generated alert was created
 *   - stats_update:  portfolio-level stats changed
 */

export type WSEventType = 'score_update' | 'new_alert' | 'stats_update';

export interface WSEvent<T = unknown> {
  type: WSEventType;
  data: T;
}

export interface ScoreUpdate {
  supplier_id: string;
  name: string;
  country: string;
  industry: string;
  financial_score: number;
  operational_score: number;
  compliance_score: number;
  geo_score: number;
  esg_score: number;
  overall_score: number;
  risk_level: string;
  trend: string;
  alert_count: number;
}

export interface NewAlertEvent {
  alert: {
    alert_id: string;
    supplier_id: string;
    supplier_name: string;
    dimension: string;
    severity: string;
    title: string;
    message: string;
    recommendations: string[];
    acknowledged: boolean;
    created_at: string;
  };
  ai_model: string;
}

export interface StatsUpdate {
  total: number;
  critical_count: number;
  high_count: number;
  avg_overall_score: number;
  unacknowledged_alert_count: number;
}

type EventHandler<T> = (data: T) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 50;
  private reconnectDelay = 2000;
  private handlers: Map<WSEventType, Set<EventHandler<unknown>>> = new Map();
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private destroyed = false;

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = `${protocol}//${window.location.host}/ws`;
  }

  connect(): void {
    if (this.destroyed) return;
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startPing();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const raw = JSON.parse(event.data) as { type: string; data?: unknown };
        // 'pong' is a server keepalive response, not a WSEventType
        if (raw.type === 'pong') return;

        const typeHandlers = this.handlers.get(raw.type as WSEventType);
        if (typeHandlers) {
          typeHandlers.forEach((handler) => handler(raw.data));
        }
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.stopPing();
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror, so reconnect is handled there
    };
  }

  disconnect(): void {
    this.destroyed = true;
    this.stopPing();
    if (this.ws) {
      this.ws.onclose = null; // Prevent reconnect
      this.ws.close();
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  on<T>(eventType: WSEventType, handler: EventHandler<T>): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler as EventHandler<unknown>);

    // Return unsubscribe function
    return () => {
      this.handlers.get(eventType)?.delete(handler as EventHandler<unknown>);
    };
  }

  private scheduleReconnect(): void {
    if (this.destroyed) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;

    const delay = Math.min(
      this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts),
      30000
    );
    this.reconnectAttempts++;

    setTimeout(() => {
      if (!this.destroyed) this.connect();
    }, delay);
  }

  private startPing(): void {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

// Singleton instance
let instance: WebSocketClient | null = null;

export function getWSClient(): WebSocketClient {
  if (!instance) {
    instance = new WebSocketClient();
  }
  return instance;
}
