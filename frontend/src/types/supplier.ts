export interface Supplier {
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
  risk_level: RiskLevel;
  trend: Trend;
  history: number[];
  alerts: Alert[];
  last_scanned_at: string;
}

export interface Alert {
  alert_id: string;
  supplier_id: string;
  supplier_name: string;
  dimension: Dimension;
  severity: Severity;
  title: string;
  message: string;
  recommendations: string[];
  acknowledged: boolean;
  created_at: string;
}

export interface Stats {
  total: number;
  critical_count: number;
  high_count: number;
  avg_overall_score: number;
  unacknowledged_alert_count: number;
}

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type Trend = 'IMPROVING' | 'STABLE' | 'DETERIORATING';
export type Severity = 'HIGH' | 'CRITICAL';
export type Dimension = 'FINANCIAL' | 'OPERATIONAL' | 'COMPLIANCE' | 'GEOPOLITICAL' | 'ESG';

export const RISK_LEVEL_COLORS: Record<RiskLevel, { bg: string; text: string; border: string; hex: string }> = {
  LOW: { bg: '#052e16', text: '#86efac', border: '#16a34a', hex: '#16a34a' },
  MEDIUM: { bg: '#422006', text: '#fde047', border: '#ca8a04', hex: '#ca8a04' },
  HIGH: { bg: '#431407', text: '#fdba74', border: '#ea580c', hex: '#ea580c' },
  CRITICAL: { bg: '#450a0a', text: '#fca5a5', border: '#dc2626', hex: '#dc2626' },
};

export const SEVERITY_COLORS: Record<Severity, { bg: string; text: string; border: string }> = {
  HIGH: { bg: '#431407', text: '#fdba74', border: '#ea580c' },
  CRITICAL: { bg: '#450a0a', text: '#fca5a5', border: '#dc2626' },
};

export const DIMENSION_LABELS: Record<Dimension, string> = {
  FINANCIAL: 'Financial',
  OPERATIONAL: 'Operational',
  COMPLIANCE: 'Compliance',
  GEOPOLITICAL: 'Geopolitical',
  ESG: 'ESG',
};

export function getScoreColor(score: number): string {
  if (score >= 80) return '#dc2626';
  if (score >= 65) return '#ea580c';
  if (score >= 40) return '#ca8a04';
  return '#16a34a';
}

export function getTrendEmoji(trend: Trend): string {
  switch (trend) {
    case 'DETERIORATING': return '🔺';
    case 'IMPROVING': return '🔻';
    case 'STABLE': return '➖';
  }
}
