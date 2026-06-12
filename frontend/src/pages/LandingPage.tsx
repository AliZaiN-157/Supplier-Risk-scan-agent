import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Shield,
  BarChart3,
  Bell,
  Users,
  ArrowRight,
  Activity,
  TrendingDown,
  GitBranch,
} from 'lucide-react';

const features = [
  {
    icon: BarChart3,
    title: 'Multi-Dimensional Scoring',
    description: 'Evaluates suppliers across 5 dimensions: Financial, Operational, Compliance, Geopolitical, and ESG with weighted scoring.',
  },
  {
    icon: Bell,
    title: 'Intelligent Alerting',
    description: 'Real-time alerts when any dimension crosses critical thresholds. AI-generated recommendations for mitigation.',
  },
  {
    icon: Users,
    title: 'Portfolio Overview',
    description: 'See your entire supplier portfolio at a glance with risk distribution charts and key metrics.',
  },
  {
    icon: TrendingDown,
    title: 'Trend Analysis',
    description: 'Track 30-day score history for each supplier with trend indicators — improving, stable, or deteriorating.',
  },
  {
    icon: Activity,
    title: 'Live Updates',
    description: 'Real-time dashboard connected via WebSocket. Score changes and alerts appear instantly without refreshing.',
  },
  {
    icon: GitBranch,
    title: 'Bulk Actions',
    description: 'Acknowledge alerts individually or in bulk. Filter by severity, status, and supplier dimension.',
  },
];

const stats = [
  { label: 'Risk Dimensions', value: '5' },
  { label: 'Suppliers Tracked', value: '15' },
  { label: 'Alert Levels', value: '4' },
  { label: 'Refresh Rate', value: 'Live' },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-lg shadow-primary/20">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-foreground">Supplier Risk Scan</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/dashboard">
              <Button variant="ghost" size="sm">Dashboard</Button>
            </Link>
            <Link to="/alerts">
              <Button variant="outline" size="sm">View Alerts</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-16 sm:pt-24 pb-12 sm:pb-16 text-center">
        <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight mb-6">
          Autonomous{' '}
          <span className="gradient-text">Supplier Risk</span>
          <br />
          Monitoring Platform
        </h1>
        <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto mb-8 sm:mb-10 leading-relaxed">
          Continuously evaluate supplier health across five risk dimensions.
          Detect financial deterioration, compliance violations, and ESG incidents
          before they disrupt your supply chain.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link to="/dashboard">
            <Button size="lg" className="gap-2">
              Enter Dashboard
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          <Link to="/suppliers">
            <Button variant="outline" size="lg">
              View Suppliers
            </Button>
          </Link>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 mb-12 sm:mb-16">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          {stats.map((stat) => (
            <div key={stat.label} className="text-center p-4 rounded-xl bg-card border border-border">
              <div className="text-2xl font-bold text-primary">{stat.value}</div>
              <div className="text-xs text-muted-foreground mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-24">
        <h2 className="text-2xl font-bold text-center mb-12">Platform Capabilities</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Card key={feature.title} className="bg-card border-border">
                <CardContent className="p-6">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                    <Icon className="w-5 h-5 text-primary" />
                  </div>
                  <h3 className="font-semibold mb-2 text-foreground">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Scoring Formula */}
      <section className="border-t border-border py-10 sm:py-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center">
          <h2 className="text-2xl font-bold mb-4">Risk Scoring Formula</h2>
          <p className="text-muted-foreground mb-8">
            Overall score is a weighted average of five dimension scores. Higher score = higher risk.
          </p>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-3 max-w-2xl mx-auto">
            {[
              { label: 'Financial', weight: '30%', color: 'bg-blue-500' },
              { label: 'Operational', weight: '25%', color: 'bg-purple-500' },
              { label: 'Compliance', weight: '20%', color: 'bg-amber-500' },
              { label: 'Geopolitical', weight: '15%', color: 'bg-rose-500' },
              { label: 'ESG', weight: '10%', color: 'bg-emerald-500' },
            ].map((item) => (
              <div key={item.label} className="text-center p-3">
                <div className={`w-full h-2 rounded-full ${item.color} mb-2`} style={{ opacity: 0.7 }} />
                <div className="text-xs font-medium text-foreground">{item.label}</div>
                <div className="text-xs text-muted-foreground">{item.weight}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-6 sm:py-8">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 text-center text-xs text-muted-foreground">
          Supplier Risk Scan Agent &bull; Built with React + FastAPI
        </div>
      </footer>
    </div>
  );
}
