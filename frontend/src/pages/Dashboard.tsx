import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import * as api from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import { getWSClient, type ScoreUpdate, type NewAlertEvent, type StatsUpdate } from '@/lib/websocket';
import type { Supplier, Alert, Stats } from '@/types/supplier';
import { RISK_LEVEL_COLORS, getScoreColor, getTrendEmoji } from '@/types/supplier';
import {
  RefreshCw, AlertTriangle, ExternalLink, FileText,
  Wifi, WifiOff,
} from 'lucide-react';

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [newAlertNotification, setNewAlertNotification] = useState<NewAlertEvent | null>(null);
  const [newAlertCount, setNewAlertCount] = useState(0);
  const [pulseAlertsSection, setPulseAlertsSection] = useState(false);

  const handleExportPDF = useCallback(() => {
    // Set the generation timestamp so the print CSS can display it
    const header = document.querySelector('.p-6.space-y-6 > div:first-child');
    if (header) {
      const now = new Date();
      const dateStr = now.toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
      header.setAttribute('data-generated', dateStr);
    }
    window.print();
  }, []);

  // Initial data load via HTTP
  const fetchInitialData = useCallback(async () => {
    try {
      const [s, supps, alerts] = await Promise.all([
        api.getStats(),
        api.getSuppliers(),
        api.getAlerts(),
      ]);
      setStats(s);
      setSuppliers(supps);
      setRecentAlerts(alerts
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 10)
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);

  // Connect WebSocket and set up listeners
  useEffect(() => {
    fetchInitialData();

    const ws = getWSClient();
    ws.connect();

    // Track connection status
    const connCheck = setInterval(() => {
      setWsConnected(ws.isConnected());
    }, 5000);

    // Listen for score updates
    const unsubScore = ws.on<ScoreUpdate>('score_update', (data) => {
      setSuppliers((prev) => {
        const updated = prev.map((s) =>
          s.supplier_id === data.supplier_id
            ? {
                ...s,
                financial_score: data.financial_score,
                operational_score: data.operational_score,
                compliance_score: data.compliance_score,
                geo_score: data.geo_score,
                esg_score: data.esg_score,
                overall_score: data.overall_score,
                risk_level: data.risk_level as Supplier['risk_level'],
                trend: data.trend as Supplier['trend'],
              }
            : s
        );
        // If the supplier wasn't in our list (shouldn't happen), add it
        if (!prev.find((s) => s.supplier_id === data.supplier_id)) {
          updated.push(data as unknown as Supplier);
        }
        return updated;
      });
    });

    // Listen for new alerts
    const unsubAlert = ws.on<NewAlertEvent>('new_alert', (data) => {
      // Show permanent notification (stays until dismissed)
      setNewAlertNotification(data);

      // Increment counter
      setNewAlertCount((c) => c + 1);

      // Pulse the alerts section
      setPulseAlertsSection(true);
      setTimeout(() => setPulseAlertsSection(false), 3000);

      // Prepend to alerts list
      setRecentAlerts((prev) => {
        const updated = [data.alert as unknown as Alert, ...prev];
        return updated.slice(0, 10);
      });
    });

    // Listen for stats updates
    const unsubStats = ws.on<StatsUpdate>('stats_update', (data) => {
      setStats(data as unknown as Stats);
    });

    return () => {
      clearInterval(connCheck);
      unsubScore();
      unsubAlert();
      unsubStats();
    };
  }, [fetchInitialData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Connection Error</h2>
          <p className="text-muted-foreground mb-4">{error}</p>
          <p className="text-xs text-muted-foreground">
            Make sure the backend is running on port 8000
          </p>
        </div>
      </div>
    );
  }

  const topHighRisk = [...suppliers]
    .sort((a, b) => b.overall_score - a.overall_score)
    .slice(0, 5);

  const riskDistribution = (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((level) => ({
    name: level,
    count: suppliers.filter((s) => s.risk_level === level).length,
    color: RISK_LEVEL_COLORS[level].hex,
  }));

  const top10ScoreData = [...suppliers]
    .sort((a, b) => b.overall_score - a.overall_score)
    .slice(0, 10)
    .reverse()
    .map((s) => ({
      name: s.name.length > 18 ? s.name.slice(0, 16) + '…' : s.name,
      score: s.overall_score,
      fill: getScoreColor(s.overall_score),
    }));

  const seedSuppliers = ['GlobalTech Manufacturing Co', 'Reliable Components Inc', 'Acme Industrial Supplies'];
  const seedProfiles = suppliers.filter((s) => seedSuppliers.includes(s.name));

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-7xl mx-auto">
      {/* New Alert Notification — stays until dismissed */}
      {newAlertNotification && (
        <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-right-5 fade-in duration-300">
          <Card className="border-primary/50 shadow-2xl shadow-primary/20 bg-card w-[calc(100vw-2rem)] sm:min-w-[380px] sm:w-auto">
            <CardContent className="p-5 flex items-start gap-4">
              <div className={`w-2 h-full rounded-full shrink-0 mt-0.5 animate-pulse ${
                newAlertNotification.alert.severity === 'CRITICAL' ? 'bg-critical' : 'bg-high'
              }`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={newAlertNotification.alert.severity.toLowerCase() as 'critical' | 'high'} className="animate-pulse">
                    🚨 NEW {newAlertNotification.alert.severity} ALERT
                  </Badge>
                  <span className="text-xs text-muted-foreground">{newAlertNotification.alert.supplier_name}</span>
                </div>
                <p className="text-sm text-foreground font-semibold">{newAlertNotification.alert.title}</p>
                <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">{newAlertNotification.alert.message}</p>
                {newAlertNotification.alert.recommendations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {newAlertNotification.alert.recommendations.slice(0, 2).map((rec, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
                        {rec}
                      </span>
                    ))}
                  </div>
                )}
                <p className="text-[10px] text-muted-foreground mt-2">
                  AI generated via {newAlertNotification.ai_model}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 -mr-2 -mt-2 h-6 w-6 p-0 rounded-full hover:bg-muted"
                onClick={() => setNewAlertNotification(null)}
              >
                <span className="text-lg leading-none">✕</span>
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
          
        </div>
        <div className="flex items-center gap-3 no-print">
          {wsConnected ? (
            <span className="flex items-center gap-1.5 text-xs text-low">
              <Wifi className="w-3 h-3" />
              Live
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-destructive">
              <WifiOff className="w-3 h-3" />
              Reconnecting...
            </span>
          )}
          <button
            onClick={handleExportPDF}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors border border-primary/20"
          >
            <FileText className="w-3.5 h-3.5" />
            Export PDF
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
        {[
          { label: 'Total Suppliers', value: stats?.total ?? '—', sub: 'Actively monitored', color: '#3b82f6' },
          { label: 'Avg Risk Score', value: stats?.avg_overall_score?.toFixed(1) ?? '—', sub: 'Portfolio health', color: getScoreColor(stats?.avg_overall_score ?? 0) },
          { label: 'Critical Risk', value: stats?.critical_count ?? 0, sub: 'Require immediate action', color: '#dc2626' },
          { label: 'High Risk', value: stats?.high_count ?? 0, sub: 'Elevated monitoring', color: '#ea580c' },
          { label: 'Unacknowledged', value: stats?.unacknowledged_alert_count ?? 0, sub: 'Pending review', color: stats?.unacknowledged_alert_count ? '#dc2626' : '#16a34a' },
        ].map((kpi) => (
          <Card key={kpi.label} className="bg-card border-border" style={{ borderLeftWidth: '4px', borderLeftColor: kpi.color }}>
            <CardContent className="p-5">
              <div className="text-[11px] text-muted-foreground uppercase tracking-widest font-medium mb-2">
                {kpi.label}
              </div>
              <div className="text-3xl font-bold mb-1" style={{ color: kpi.color }}>
                {kpi.value}
              </div>
              <div className="text-xs text-muted-foreground">
                {kpi.sub}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Risk Level Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 min-w-0">
              <ResponsiveContainer width="100%" height={230}>
                <BarChart
                  data={riskDistribution.filter((d) => d.count > 0)}
                  layout="vertical"
                  margin={{ left: 80, right: 20, top: 5, bottom: 5 }}
                  barSize={28}
                  barGap={4}
                >
                  <XAxis type="number" tick={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fill: '#a0a0a0', fontSize: 12, fontWeight: 600 }}
                    width={80}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#1a1a1a',
                      border: '1px solid #333',
                      borderRadius: '8px',
                    }}
                    labelStyle={{ color: '#f0f0f0' }}
                    itemStyle={{ color: '#f0f0f0' }}
                    formatter={(value: unknown) => [`${(value as number) ?? 0}`, 'Count']}
                  />
                  <Bar dataKey="count" stackId="a" radius={[0, 4, 4, 0]}>
                    {riskDistribution.filter((d) => d.count > 0).map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-center gap-5 mt-2">
              {riskDistribution.map((item) => (
                <div key={item.name} className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-xs text-muted-foreground">
                    {item.name} ({item.count})
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Highest Risk Suppliers</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 min-w-0">
              <ResponsiveContainer width="100%" height={256}>
                <BarChart data={top10ScoreData} layout="vertical" margin={{ left: 0, right: 20, top: 0, bottom: 0 }}>
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: '#a0a0a0', fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={140}
                    tick={{ fill: '#a0a0a0', fontSize: 11 }}
                  />
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
                  <Bar dataKey="score" radius={[0, 4, 4, 0]} maxBarSize={16}>
                    {top10ScoreData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* New Alert Counter Badge */}
      {newAlertCount > 0 && (
        <div className="fixed bottom-4 right-4 z-50 animate-in fade-in zoom-in">
          <Button
            variant="outline"
            size="sm"
            className="gap-2 bg-card border-primary/30 shadow-lg"
            onClick={() => {
              setNewAlertCount(0);
              document.getElementById('recent-alerts')?.scrollIntoView({ behavior: 'smooth' });
            }}
          >
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="text-xs font-semibold">{newAlertCount} new alert{newAlertCount !== 1 ? 's' : ''}</span>
          </Button>
        </div>
      )}

      {/* Top 5 High Risk Table */}
      <Card className="bg-card border-border">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold">Top 5 High-Risk Suppliers</CardTitle>
          <Link to="/suppliers">
            <Button variant="ghost" size="sm" className="gap-1 text-xs">
              View All <ExternalLink className="w-3 h-3" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent className="p-0 sm:p-6">
          <div className="overflow-x-auto">
          <Table className="min-w-[600px]">
            <TableHeader>
              <TableRow>
                <TableHead>Supplier</TableHead>
                <TableHead>Country</TableHead>
                <TableHead>Overall Score</TableHead>
                <TableHead>Risk Level</TableHead>
                <TableHead>Trend</TableHead>
                <TableHead>Alerts</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {topHighRisk.map((supplier) => (
                <TableRow key={supplier.supplier_id}>
                  <TableCell className="font-medium text-foreground">{supplier.name}</TableCell>
                  <TableCell className="text-muted-foreground">{supplier.country}</TableCell>
                  <TableCell>
                    <span className="font-semibold" style={{ color: getScoreColor(supplier.overall_score) }}>
                      {supplier.overall_score.toFixed(1)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={supplier.risk_level.toLowerCase() as 'critical' | 'high' | 'medium' | 'low'}>
                      {supplier.risk_level}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">
                      {getTrendEmoji(supplier.trend)} {supplier.trend}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{supplier.alerts.length}</TableCell>
                  <TableCell>
                    <Link to={`/suppliers/${supplier.supplier_id}`}>
                      <Button variant="ghost" size="sm" className="text-xs">Details</Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          </div>
        </CardContent>
      </Card>

      {/* Seed Supplier Highlights */}
      {seedProfiles.length > 0 && (
        <Card className="bg-card border-border print-hide">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">🏷️ Seed Supplier Profiles</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
              {seedProfiles.map((s) => (
                <Link key={s.supplier_id} to={`/suppliers/${s.supplier_id}`}>
                  <div className="p-4 rounded-lg border border-border bg-card/50 hover:bg-accent transition-all card-hover">
                    <div className="font-semibold text-sm text-foreground mb-1">{s.name}</div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
                      <span>{s.country}</span>
                      <span>·</span>
                      <span>{s.industry}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <Badge variant={s.risk_level.toLowerCase() as 'critical' | 'high' | 'medium' | 'low'}>
                        {s.risk_level}
                      </Badge>
                      <span className="text-sm font-bold" style={{ color: getScoreColor(s.overall_score) }}>
                        {s.overall_score.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                      <span>{getTrendEmoji(s.trend)} {s.trend}</span>
                      <span>·</span>
                      <span>{s.alerts.length} alert{s.alerts.length !== 1 ? 's' : ''}</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Alerts Feed */}
      <Card id="recent-alerts" className={`bg-card border-border transition-all duration-300 ${
        pulseAlertsSection ? 'ring-2 ring-primary/30 shadow-lg shadow-primary/10' : ''
      }`}>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold">Recent Alerts</CardTitle>
          <Link to="/alerts">
            <Button variant="ghost" size="sm" className="gap-1 text-xs">
              View All <ExternalLink className="w-3 h-3" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {recentAlerts.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No recent alerts</p>
            ) : (
              recentAlerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  className="flex items-start gap-4 p-3 rounded-lg border border-border bg-card/50 hover:bg-accent transition-colors"
                >
                  <div
                    className={`w-1 h-10 rounded-full shrink-0 mt-1 ${
                      alert.severity === 'CRITICAL' ? 'bg-critical' : 'bg-high'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={alert.severity.toLowerCase() as 'critical' | 'high'}>
                        {alert.severity}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{alert.supplier_name}</span>
                    </div>
                    <p className="text-sm text-foreground truncate">{alert.title}</p>
                    <p className="text-xs text-muted-foreground mt-1">{formatRelativeTime(alert.created_at)}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
