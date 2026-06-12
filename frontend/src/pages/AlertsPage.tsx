import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import * as api from '@/lib/api';
import { formatRelativeTime, cn } from '@/lib/utils';
import { getWSClient, type NewAlertEvent } from '@/lib/websocket';
import type { Alert, Dimension } from '@/types/supplier';
import { DIMENSION_LABELS } from '@/types/supplier';
import { RefreshCw, CheckCheck, Filter, Wifi, WifiOff } from 'lucide-react';

const DIMENSIONS: Dimension[] = ['FINANCIAL', 'OPERATIONAL', 'COMPLIANCE', 'GEOPOLITICAL', 'ESG'];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [severity, setSeverity] = useState<string>('ALL');
  const [status, setStatus] = useState<string>('ALL');
  const [dimension, setDimension] = useState<string>('ALL');
  const [acknowledging, setAcknowledging] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const fetchCounter = useRef(0);

  const fetchAlerts = useCallback(async (isInitial = false) => {
    if (isInitial) fetchCounter.current += 1;
    try {
      const params: Record<string, string | boolean> = {};
      if (severity !== 'ALL') params.severity = severity;
      if (status === 'OPEN') params.acknowledged = false;
      if (status === 'ACKNOWLEDGED') params.acknowledged = true;
      if (dimension !== 'ALL') {
        const dimKey = dimension as Dimension;
        const allAlerts = await api.getAlerts(params);
        setAlerts(allAlerts.filter((a) => a.dimension === dimKey));
      } else {
        const allAlerts = await api.getAlerts(params);
        setAlerts(allAlerts);
      }
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    } finally {
      setLoading(false);
    }
  }, [severity, status, dimension]);

  // Initial load
  useEffect(() => {
    fetchAlerts(true);

    // WebSocket listener for new alerts
    const ws = getWSClient();
    ws.connect();

    const unsub = ws.on<NewAlertEvent>('new_alert', (data) => {
      // Add to alerts list if it matches current filters
      setAlerts((prev) => {
        const alert = data.alert as unknown as Alert;
        // Don't add duplicates
        if (prev.some((a) => a.alert_id === alert.alert_id)) return prev;
        // Apply current filters
        if (severity !== 'ALL' && alert.severity !== severity) return prev;
        if (status === 'ACKNOWLEDGED') return prev; // new alerts are never acknowledged
        if (dimension !== 'ALL' && alert.dimension !== dimension) return prev;
        return [alert, ...prev];
      });
    });

    // Track connection
    const connCheck = setInterval(() => {
      setWsConnected(ws.isConnected());
    }, 5000);

    return () => {
      unsub();
      clearInterval(connCheck);
    };
  }, [fetchAlerts, severity, status, dimension]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const unackedAlerts = alerts.filter((a) => !a.acknowledged);

  const toggleAll = () => {
    if (selected.size === unackedAlerts.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(unackedAlerts.map((a) => a.alert_id)));
    }
  };

  const handleBulkAck = async () => {
    if (selected.size === 0) return;
    setAcknowledging(true);
    try {
      await api.bulkAcknowledgeAlerts(Array.from(selected));
      setSelected(new Set());
      await fetchAlerts();
    } catch (err) {
      console.error('Bulk acknowledge failed:', err);
    } finally {
      setAcknowledging(false);
    }
  };

  const handleSingleAck = async (alertId: string) => {
    try {
      await api.acknowledgeAlert(alertId);
      await fetchAlerts();
    } catch (err) {
      console.error('Acknowledge failed:', err);
    }
  };

  const criticalCount = alerts.filter((a) => a.severity === 'CRITICAL').length;
  const highCount = alerts.filter((a) => a.severity === 'HIGH').length;
  const unackedCount = alerts.filter((a) => !a.acknowledged).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Alerts Center</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage and review risk alerts across your portfolio
          </p>
        </div>
        <div className="flex items-center gap-2">
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
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        {[
          { label: 'Total Alerts', value: alerts.length, color: '#f0f0f0' },
          { label: 'Critical', value: criticalCount, color: '#dc2626' },
          { label: 'High', value: highCount, color: '#ea580c' },
          { label: 'Unacknowledged', value: unackedCount, color: unackedCount > 0 ? '#dc2626' : '#16a34a' },
        ].map((item) => (
          <Card key={item.label} className="bg-card border-border">
            <CardContent className="p-5">
              <div className="text-xs text-muted-foreground uppercase tracking-wider font-medium mb-2">
                {item.label}
              </div>
              <div className="text-2xl font-bold" style={{ color: item.color }}>
                {item.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <Card className="bg-card border-border">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
            <Filter className="w-4 h-4 text-muted-foreground hidden sm:block" />
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="h-9 w-full sm:w-auto rounded-md border border-input bg-transparent px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
            </select>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="h-9 w-full sm:w-auto rounded-md border border-input bg-transparent px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="ALL">All Status</option>
              <option value="OPEN">Open</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
            </select>
            <select
              value={dimension}
              onChange={(e) => setDimension(e.target.value)}
              className="h-9 w-full sm:w-auto rounded-md border border-input bg-transparent px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="ALL">All Dimensions</option>
              {DIMENSIONS.map((d) => (
                <option key={d} value={d}>{DIMENSION_LABELS[d]}</option>
              ))}
            </select>
            <Button variant="outline" size="sm" onClick={() => fetchAlerts()} className="gap-2 sm:ml-auto">
              <RefreshCw className="w-3 h-3" />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Action Bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-4 p-4 rounded-lg bg-primary/5 border border-primary/20 animate-fade-in">
          <span className="text-sm font-medium text-foreground">
            {selected.size} alert{selected.size !== 1 ? 's' : ''} selected
          </span>
          <Button
            size="sm"
            onClick={handleBulkAck}
            disabled={acknowledging}
            className="gap-2"
          >
            <CheckCheck className="w-4 h-4" />
            {acknowledging ? 'Acknowledging...' : 'Acknowledge Selected'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelected(new Set())}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Alert Table */}
      <Card className="bg-card border-border">
        <CardContent className="p-0">
          {alerts.length === 0 ? (
            <div className="text-center py-16 animate-fade-in">
              <div className="w-16 h-16 rounded-full bg-low-bg flex items-center justify-center mx-auto mb-4">
                <CheckCheck className="w-8 h-8 text-low" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">All Clear!</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                All alerts have been acknowledged. Your supplier portfolio is up to date.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
            <Table className="min-w-[700px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      checked={selected.size === unackedAlerts.length && unackedAlerts.length > 0}
                      onCheckedChange={toggleAll}
                    />
                  </TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Supplier</TableHead>
                  <TableHead>Dimension</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-28">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((alert) => (
                  <TableRow
                    key={alert.alert_id}
                    className={cn(alert.acknowledged && 'opacity-50')}
                  >
                    <TableCell>
                      {!alert.acknowledged && (
                        <Checkbox
                          checked={selected.has(alert.alert_id)}
                          onCheckedChange={() => toggleSelect(alert.alert_id)}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={alert.severity.toLowerCase() as 'critical' | 'high'}>
                        {alert.severity}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/suppliers/${alert.supplier_id}`}
                        className="text-sm text-primary hover:underline font-medium"
                      >
                        {alert.supplier_name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">
                        {DIMENSION_LABELS[alert.dimension]}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-foreground truncate max-w-[200px] block">
                        {alert.title}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground whitespace-nowrap">
                        {formatRelativeTime(alert.created_at)}
                      </span>
                    </TableCell>
                    <TableCell>
                      {alert.acknowledged ? (
                        <span className="text-xs text-low">✅ Acknowledged</span>
                      ) : (
                        <span className="text-xs text-high">⏳ Open</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {!alert.acknowledged && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleSingleAck(alert.alert_id)}
                          className="text-xs"
                        >
                          Acknowledge
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
