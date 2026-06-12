import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import * as api from '@/lib/api';
import type { Supplier } from '@/types/supplier';
import { RISK_LEVEL_COLORS, getScoreColor, getTrendEmoji } from '@/types/supplier';
import { Search, ArrowUpDown, ExternalLink, AlertTriangle } from 'lucide-react';

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<'overall_score' | 'name'>('overall_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSuppliers()
      .then(setSuppliers)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = suppliers
    .filter((s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.country.toLowerCase().includes(search.toLowerCase()) ||
      s.industry.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const mul = sortDir === 'asc' ? 1 : -1;
      if (sortField === 'overall_score') return mul * (a.overall_score - b.overall_score);
      return mul * a.name.localeCompare(b.name);
    });

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-muted-foreground">Loading suppliers...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <AlertTriangle className="w-10 h-10 text-destructive mx-auto mb-3" />
          <p className="text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Suppliers</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {suppliers.length} suppliers in your portfolio
        </p>
      </div>

      {/* Search & Sort */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by name, country, or industry..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => toggleSort('overall_score')}
          className="gap-2"
        >
          <ArrowUpDown className="w-3 h-3" />
          Score {sortField === 'overall_score' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
        </Button>
      </div>

      {/* Supplier Cards */}
      <div className="grid gap-4">
        {filtered.map((supplier) => (
          <Link
            key={supplier.supplier_id}
            to={`/suppliers/${supplier.supplier_id}`}
            className="block"
          >
            <Card className="bg-card border-border hover:border-primary/30 transition-all duration-200">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4 flex-1">
                    {/* Score Circle */}
                    <div
                      className="w-14 h-14 rounded-full flex items-center justify-center font-bold text-sm shrink-0"
                      style={{
                        backgroundColor: `${getScoreColor(supplier.overall_score)}20`,
                        color: getScoreColor(supplier.overall_score),
                        border: `2px solid ${getScoreColor(supplier.overall_score)}`,
                      }}
                    >
                      {supplier.overall_score.toFixed(0)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-foreground truncate">{supplier.name}</h3>
                        <Badge variant={supplier.risk_level.toLowerCase() as 'critical' | 'high' | 'medium' | 'low'}>
                          {supplier.risk_level}
                        </Badge>
                      </div>
                      <div className="flex items-center flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        <span>{supplier.country}</span>
                        <span className="hidden sm:inline">·</span>
                        <span className="hidden sm:inline">{supplier.industry}</span>
                        <span>·</span>
                        <span>{getTrendEmoji(supplier.trend)} {supplier.trend}</span>
                        <span>·</span>
                        <span>{supplier.alerts.length} alert{supplier.alerts.length !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                  </div>

                  {/* Dimension mini bars */}
                  <div className="hidden md:flex items-center gap-4">
                    {(['financial_score', 'operational_score', 'compliance_score', 'geo_score', 'esg_score'] as const).map((key) => {
                      const score = supplier[key];
                      return (
                        <div key={key} className="text-center min-w-[48px]">
                          <div className="h-1.5 w-12 rounded-full bg-muted overflow-hidden mb-1">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${score}%`,
                                backgroundColor: getScoreColor(score),
                              }}
                            />
                          </div>
                          <span className="text-[10px] text-muted-foreground">
                            {key === 'financial_score' ? 'Fin' :
                             key === 'operational_score' ? 'Ops' :
                             key === 'compliance_score' ? 'Cmp' :
                             key === 'geo_score' ? 'Geo' : 'ESG'}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <ExternalLink className="w-4 h-4 text-muted-foreground ml-4 shrink-0" />
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12">
          <p className="text-muted-foreground">No suppliers match your search.</p>
        </div>
      )}
    </div>
  );
}
