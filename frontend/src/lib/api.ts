import type { Supplier, Alert, Stats } from '@/types/supplier';

const API_BASE = '/api';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export function getSuppliers(): Promise<Supplier[]> {
  return fetchJSON<Supplier[]>('/suppliers');
}

export function getSupplier(id: string): Promise<Supplier> {
  return fetchJSON<Supplier>(`/suppliers/${id}`);
}

export function getAlerts(params?: {
  severity?: string;
  acknowledged?: boolean;
  supplier_id?: string;
}): Promise<Alert[]> {
  const qs = new URLSearchParams();
  if (params?.severity) qs.set('severity', params.severity);
  if (params?.acknowledged !== undefined) qs.set('acknowledged', String(params.acknowledged));
  if (params?.supplier_id) qs.set('supplier_id', params.supplier_id);
  const query = qs.toString();
  return fetchJSON<Alert[]>(`/alerts${query ? `?${query}` : ''}`);
}

export function getStats(): Promise<Stats> {
  return fetchJSON<Stats>('/stats');
}

export function acknowledgeAlert(alertId: string): Promise<Alert> {
  return fetchJSON<Alert>(`/alerts/${alertId}/acknowledge`, { method: 'PATCH' });
}

export function bulkAcknowledgeAlerts(alertIds: string[]): Promise<{ acknowledged_count: number }> {
  return fetchJSON<{ acknowledged_count: number }>('/alerts/bulk-acknowledge', {
    method: 'POST',
    body: JSON.stringify({ alert_ids: alertIds }),
  });
}
