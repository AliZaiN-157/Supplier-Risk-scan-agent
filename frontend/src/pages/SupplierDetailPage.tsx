import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ReferenceLine,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import * as api from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import type { Supplier } from '@/types/supplier';
import { DIMENSION_LABELS, getScoreColor, getTrendEmoji } from '@/types/supplier';
import { ArrowLeft, AlertTriangle, RefreshCw } from 'lucide-react';

const RADAR_DIMENSIONS = [
  { key: 'financial_score', label: 'Financial' },
  { key: 'operational_score', label: 'Operational' },
  { key: 'compliance_score', label: 'Compliance' },
  { key: 'geo_score', label: 'Geopolitical' },
  { key: 'esg_score', label: 'ESG' },
] as const;

export default function SupplierDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getSupplier(id)
      .then(setSupplier)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !supplier) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <AlertTriangle className="w-10 h-10 text-destructive mx-auto mb-3" />
          <p className="text-muted-foreground">{error || 'Supplier not found'}</p>
          <Link to="/suppliers">
            <Button variant="outline" className="mt-4">Back to Suppliers</Button>
          </Link>
        </div>
      </div>
    );
  }

  const dimScores = RADAR_DIMENSIONS.map((d) => ({
    dimension: d.label,
    score: supplier[d.key],
    fullMark: 100,
  }));

  const historyData = supplier.history.map((score, i) => ({
    day: i + 1,
    score,
  }));

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-7xl mx-auto">
      {/* Back Button */}
      <Link to="/suppliers">
        <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground">
          <ArrowLeft className="w-4 h-4" />
          Back to Suppliers
        </Button>
      </Link>

      {/* Supplier Header */}
      <Card className="bg-card border-border">
        <CardContent className="p-4 sm:p-6">
          <div className="flex flex-col sm:flex-row items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{supplier.name}</h1>
              <p className="text-sm text-muted-foreground mt-1">
                {supplier.country} &bull; {supplier.industry}
              </p>
              <div className="flex items-center gap-3 mt-3">
                <Badge variant={supplier.risk_level.toLowerCase() as 'critical' | 'high' | 'medium' | 'low'}>
                  {supplier.risk_level}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {getTrendEmoji(supplier.trend)} {supplier.trend}
                </span>
                <span className="text-sm text-muted-foreground">
                  {supplier.alerts.length} active alert{supplier.alerts.length !== 1 ? 's' : ''}
                </span>
              </div>
            </div>

            {/* Score Gauge */}
            <div className="flex flex-col items-center gap-2 shrink-0 self-center sm:self-start">
              <div className="relative w-32 h-32 sm:w-36 sm:h-36">
                <svg className="w-full h-full" viewBox="0 0 160 160">
                  {/* Outer glow */}
                  <circle
                    cx="80"
                    cy="80"
                    r="68"
                    fill="none"
                    stroke={getScoreColor(supplier.overall_score)}
                    strokeWidth="1"
                    strokeOpacity="0.15"
                  />
                  {/* Background track */}
                  <circle
                    cx="80"
                    cy="80"
                    r="60"
                    fill="none"
                    stroke="#1e1e1e"
                    strokeWidth="12"
                    strokeLinecap="round"
                    transform="rotate(-90 80 80)"
                  />
                  {/* Score arc */}
                  <circle
                    cx="80"
                    cy="80"
                    r="60"
                    fill="none"
                    stroke={getScoreColor(supplier.overall_score)}
                    strokeWidth="12"
                    strokeLinecap="round"
                    strokeDasharray={`${(supplier.overall_score / 100) * 377} 377`}
                    transform="rotate(-90 80 80)"
                    className="transition-all duration-1000 ease-out"
                    style={{ filter: `drop-shadow(0 0 8px ${getScoreColor(supplier.overall_score)}40)` }}
                  />
                  {/* Center text */}
                  <text
                    x="80"
                    y="74"
                    textAnchor="middle"
                    fill={getScoreColor(supplier.overall_score)}
                    style={{ fontSize: '40px', fontWeight: 700 }}
                  >
                    {supplier.overall_score.toFixed(0)}
                  </text>
                  <text
                    x="80"
                    y="98"
                    textAnchor="middle"
                    fill="#71717a"
                    style={{ fontSize: '12px' }}
                  >
                    / 100
                  </text>
                </svg>
              </div>
              <div className="text-center">
                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: getScoreColor(supplier.overall_score) }}>
                  Risk Score
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Radar Chart */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Dimension Scores — Radar</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={dimScores} cx="50%" cy="50%" outerRadius="75%">
                  <PolarGrid stroke="#333" />
                  <PolarAngleAxis
                    dataKey="dimension"
                    tick={{ fill: '#a0a0a0', fontSize: 11 }}
                  />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#a0a0a0', fontSize: 10 }} />
                  <Radar
                    name="Score"
                    dataKey="score"
                    stroke="#3b82f6"
                    fill="#3b82f6"
                    fillOpacity={0.15}
                    strokeWidth={2}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#1a1a1a',
                      border: '1px solid #333',
                      borderRadius: '8px',
                    }}
                    labelStyle={{ color: '#f0f0f0' }}
                    itemStyle={{ color: '#f0f0f0' }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* History Timeline */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">30-Day Score History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <XAxis
                    dataKey="day"
                    tick={{ fill: '#a0a0a0', fontSize: 11 }}
                    label={{ value: 'Day', position: 'insideBottom', offset: -5, fill: '#a0a0a0', fontSize: 11 }}
                  />
                  <YAxis domain={[0, 100]} tick={{ fill: '#a0a0a0', fontSize: 11 }} />
                  {/* Threshold bands */}
                  <ReferenceLine y={75} stroke="#dc2626" strokeDasharray="4 4" strokeOpacity={0.5} />
                  <ReferenceLine y={60} stroke="#ea580c" strokeDasharray="4 4" strokeOpacity={0.5} />
                  <Tooltip
                    contentStyle={{
                      background: '#1a1a1a',
                      border: '1px solid #333',
                      borderRadius: '8px',
                    }}
                    labelStyle={{ color: '#f0f0f0' }}
                    itemStyle={{ color: '#f0f0f0' }}
                    formatter={(value: unknown) => {
                      const v = typeof value === 'number' ? value : 0;
                      return [`${v.toFixed(1)}`, 'Score'];
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, fill: '#3b82f6' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mt-3 text-xs">
              <span className="text-muted-foreground">
                Start: {historyData[0]?.score.toFixed(1) ?? '—'}
              </span>
              <span className="text-muted-foreground">
                Current: {historyData[historyData.length - 1]?.score.toFixed(1) ?? '—'}
              </span>
              <span className="text-muted-foreground">
                Range: {Math.min(...supplier.history).toFixed(1)} — {Math.max(...supplier.history).toFixed(1)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Dimension Score Bars */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Dimension Scores — Detail</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {dimScores.map((d) => (
              <div key={d.dimension}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-medium text-foreground">{d.dimension}</span>
                  <span className="text-sm font-semibold" style={{ color: getScoreColor(d.score) }}>
                    {d.score.toFixed(1)}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${d.score}%`,
                      backgroundColor: getScoreColor(d.score),
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Alerts */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-sm font-semibold">
            Active Alerts ({supplier.alerts.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {supplier.alerts.length === 0 ? (
              <div className="text-center py-8">
                <div className="text-3xl mb-2">✅</div>
                <p className="text-sm text-muted-foreground">No alerts for this supplier.</p>
              </div>
            ) : (
              supplier.alerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  className="p-4 rounded-lg border border-border bg-card/50"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={alert.severity.toLowerCase() as 'critical' | 'high'}>
                        {alert.severity}
                      </Badge>
                      <span className="text-sm font-medium text-foreground">
                        {DIMENSION_LABELS[alert.dimension]}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatRelativeTime(alert.created_at)}
                    </span>
                  </div>
                  <h4 className="text-sm font-medium text-foreground mb-1">{alert.title}</h4>
                  <p className="text-sm text-muted-foreground mb-3">{alert.message}</p>
                  {alert.recommendations.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Recommendations:</p>
                      <ul className="list-disc list-inside space-y-0.5">
                        {alert.recommendations.map((rec, i) => (
                          <li key={i} className="text-xs text-muted-foreground">{rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
