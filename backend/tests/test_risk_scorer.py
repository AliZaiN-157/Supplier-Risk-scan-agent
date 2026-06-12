"""Tests for risk scoring logic."""
import pytest
from app.risk_scorer import (
    compute_financial_score,
    compute_operational_score,
    compute_compliance_score,
    compute_geo_score,
    compute_esg_score,
    compute_overall_score,
    determine_risk_level,
    determine_trend,
    RiskLevel,
    Trend,
)


class TestFinancialScore:
    def test_low_credit_good_metrics(self):
        """Credit score 750, profit margin 20%, DSO 30, debt ratio 0.2 -> low risk."""
        score = compute_financial_score(credit_score=750, profit_margin=20.0, dso=30, debt_ratio=0.2)
        assert 0 <= score <= 100
        assert score < 40  # Should be low risk

    def test_poor_credit_bad_metrics(self):
        """Credit score 350, profit margin -5%, DSO 110, debt ratio 0.8 -> high risk."""
        score = compute_financial_score(credit_score=350, profit_margin=-5.0, dso=110, debt_ratio=0.8)
        assert 0 <= score <= 100
        assert score > 60  # Should be high risk

    def test_negative_margin_penalty(self):
        """Negative profit margin adds penalty."""
        score_neg = compute_financial_score(credit_score=600, profit_margin=-3.0, dso=45, debt_ratio=0.4)
        score_pos = compute_financial_score(credit_score=600, profit_margin=10.0, dso=45, debt_ratio=0.4)
        assert score_neg > score_pos  # Negative should be higher risk

    def test_high_dso_penalty(self):
        """DSO > 90 adds penalty."""
        score_high_dso = compute_financial_score(credit_score=600, profit_margin=10.0, dso=100, debt_ratio=0.4)
        score_low_dso = compute_financial_score(credit_score=600, profit_margin=10.0, dso=40, debt_ratio=0.4)
        assert score_high_dso > score_low_dso

    def test_score_clamped(self):
        """Score should be clamped to 0-100."""
        # Very bad: credit 300, margin -5%, dso 120, debt 0.9
        score = compute_financial_score(credit_score=300, profit_margin=-5.0, dso=120, debt_ratio=0.9)
        assert 0 <= score <= 100
        # Very good: credit 850, margin 25%, dso 20, debt 0.1
        score = compute_financial_score(credit_score=850, profit_margin=25.0, dso=20, debt_ratio=0.1)
        assert 0 <= score <= 100


class TestOperationalScore:
    def test_high_on_time_low_defect(self):
        score = compute_operational_score(on_time_delivery_pct=98.0, defect_rate_pct=0.5, capacity_utilization_pct=75.0)
        assert 0 <= score <= 100
        assert score < 40

    def test_low_on_time_high_defect(self):
        score = compute_operational_score(on_time_delivery_pct=62.0, defect_rate_pct=7.0, capacity_utilization_pct=50.0)
        assert 0 <= score <= 100
        assert score > 60

    def test_below_80_otd_penalty(self):
        """Below 80% on-time delivery adds penalty."""
        score_low = compute_operational_score(on_time_delivery_pct=70.0, defect_rate_pct=1.0, capacity_utilization_pct=75.0)
        score_high = compute_operational_score(on_time_delivery_pct=90.0, defect_rate_pct=1.0, capacity_utilization_pct=75.0)
        assert score_low > score_high

    def test_above_3_pct_defect_penalty(self):
        """Above 3% defect rate adds penalty."""
        score_high_defect = compute_operational_score(on_time_delivery_pct=85.0, defect_rate_pct=5.0, capacity_utilization_pct=75.0)
        score_low_defect = compute_operational_score(on_time_delivery_pct=85.0, defect_rate_pct=1.0, capacity_utilization_pct=75.0)
        assert score_high_defect > score_low_defect


class TestComplianceScore:
    def test_no_violations_valid_certs(self):
        score = compute_compliance_score(violations_last_12mo=0, cert_expiry_days=300)
        assert 0 <= score <= 100
        assert score < 40

    def test_violations_and_expiring_certs(self):
        score = compute_compliance_score(violations_last_12mo=3, cert_expiry_days=30)
        assert 0 <= score <= 100
        assert score > 60

    def test_expiry_within_60_days_penalty(self):
        score_expiring = compute_compliance_score(violations_last_12mo=0, cert_expiry_days=30)
        score_valid = compute_compliance_score(violations_last_12mo=0, cert_expiry_days=200)
        assert score_expiring > score_valid


class TestGeoScore:
    def test_low_risk_country(self):
        """Low country risk index -> low geo score (low risk)."""
        score = compute_geo_score(country_risk_index=15, trade_restrictions=False)
        assert 0 <= score <= 100
        assert score < 40

    def test_high_risk_country(self):
        """High country risk index -> high geo score."""
        score = compute_geo_score(country_risk_index=85, trade_restrictions=True)
        assert 0 <= score <= 100
        assert score > 60

    def test_trade_restrictions_penalty(self):
        score_no_rest = compute_geo_score(country_risk_index=50, trade_restrictions=False)
        score_rest = compute_geo_score(country_risk_index=50, trade_restrictions=True)
        assert score_rest > score_no_rest


class TestESGScore:
    def test_good_esg(self):
        score = compute_esg_score(environmental=20, social=15, governance=10)
        assert 0 <= score <= 100
        assert score < 40

    def test_poor_esg(self):
        score = compute_esg_score(environmental=85, social=80, governance=75)
        assert 0 <= score <= 100
        assert score > 60

    def test_average_of_three(self):
        """ESG is average of three sub-scores."""
        score = compute_esg_score(environmental=50, social=50, governance=50)
        assert score == 50.0


class TestOverallScore:
    def test_weighted_average(self):
        """Formula: 0.30*F + 0.25*O + 0.20*C + 0.15*G + 0.10*E"""
        score = compute_overall_score(
            financial=100, operational=100, compliance=100, geo=100, esg=100
        )
        assert score == 100.0

    def test_all_zero(self):
        score = compute_overall_score(
            financial=0, operational=0, compliance=0, geo=0, esg=0
        )
        assert score == 0.0

    def test_mixed_scores(self):
        score = compute_overall_score(
            financial=80, operational=40, compliance=20, geo=10, esg=50
        )
        expected = 0.30 * 80 + 0.25 * 40 + 0.20 * 20 + 0.15 * 10 + 0.10 * 50
        assert score == expected

    def test_weights_correct(self):
        """Verify the formula weights are correct."""
        # If all are 100 except financial is 0
        score = compute_overall_score(
            financial=0, operational=100, compliance=100, geo=100, esg=100
        )
        expected = 0.30 * 0 + 0.25 * 100 + 0.20 * 100 + 0.15 * 100 + 0.10 * 100
        assert score == expected


class TestDetermineRiskLevel:
    def test_low_0_to_39(self):
        assert determine_risk_level(0) == RiskLevel.LOW
        assert determine_risk_level(20) == RiskLevel.LOW
        assert determine_risk_level(39) == RiskLevel.LOW

    def test_medium_40_to_59(self):
        assert determine_risk_level(40) == RiskLevel.MEDIUM
        assert determine_risk_level(50) == RiskLevel.MEDIUM
        assert determine_risk_level(59) == RiskLevel.MEDIUM

    def test_high_60_to_74(self):
        assert determine_risk_level(60) == RiskLevel.HIGH
        assert determine_risk_level(65) == RiskLevel.HIGH
        assert determine_risk_level(74) == RiskLevel.HIGH

    def test_critical_75_to_100(self):
        assert determine_risk_level(75) == RiskLevel.CRITICAL
        assert determine_risk_level(90) == RiskLevel.CRITICAL
        assert determine_risk_level(100) == RiskLevel.CRITICAL


class TestDetermineTrend:
    def test_improving_when_recent_lower(self):
        """If last 7 days avg < previous 7 days avg -> IMPROVING (score decreased means improving)."""
        history = [50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37]
        assert determine_trend(history) == Trend.IMPROVING

    def test_deteriorating_when_recent_higher(self):
        history = [30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56]
        assert determine_trend(history) == Trend.DETERIORATING

    def test_stable_when_no_significant_change(self):
        history = [50, 51, 49, 50, 51, 49, 50, 51, 49, 50, 51, 49, 50, 51]
        assert determine_trend(history) == Trend.STABLE

    def test_insufficient_history_returns_stable(self):
        assert determine_trend([50]) == Trend.STABLE
        assert determine_trend([]) == Trend.STABLE


class TestEdgeCases:
    def test_financial_score_boundary(self):
        """Test boundary conditions for financial score."""
        score = compute_financial_score(credit_score=300, profit_margin=-5.0, dso=120, debt_ratio=1.0)
        assert 0 <= score <= 100
        score = compute_financial_score(credit_score=850, profit_margin=25.0, dso=20, debt_ratio=0.0)
        assert 0 <= score <= 100

    def test_operational_score_boundary(self):
        score = compute_operational_score(on_time_delivery_pct=99.0, defect_rate_pct=0.1, capacity_utilization_pct=100.0)
        assert 0 <= score <= 100
        score = compute_operational_score(on_time_delivery_pct=60.0, defect_rate_pct=8.0, capacity_utilization_pct=30.0)
        assert 0 <= score <= 100
