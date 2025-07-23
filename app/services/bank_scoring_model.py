from typing import Dict, Any, List
import pandas as pd
import numpy as np
from app.schemas.response import RuleBreakdown
from app.utils.tenant_config import get_tenant_config

async def calculate_bank_behavioral_score(
    customer_id: str,
    bank_features: Dict[str, Any],
    anomalies_detected: List[Any],
    company_id: str
) -> Dict[str, Any]:
    """
    Calculates the behavioral score specifically for bank transaction data.
    Score range: 0-1000
    """
    
    # Initialize base score
    base_score = 500  # Start from middle
    
    tenant_config = await get_tenant_config(company_id)
    scoring_weights = tenant_config.get("bank_scoring_weights", {})
    rule_engine_breakdown: List[RuleBreakdown] = []
    
    # Bank-specific scoring rules
    
    # Rule 1: Income Consistency (0-200 points)
    income_consistency = bank_features.get("income_consistency", 0)
    income_score = income_consistency * 200
    base_score += (income_score - 100)  # Adjust from base
    rule_engine_breakdown.append(RuleBreakdown(
        rule_name="Income Consistency",
        condition_met=f"Income consistency score: {income_consistency:.2f}",
        adjustment=income_score - 100,
        new_score_after_adjustment=base_score
    ))
    
    # Rule 2: Average Balance (0-150 points)
    avg_balance = bank_features.get("avg_daily_balance", 0)
    if avg_balance > 100000:  # High balance
        balance_bonus = scoring_weights.get("high_balance_bonus", 100)
        base_score += balance_bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Average Balance",
            condition_met=f"Average balance: {avg_balance:.2f} > 100,000",
            adjustment=balance_bonus,
            new_score_after_adjustment=base_score
        ))
    elif avg_balance < 5000:  # Low balance
        balance_penalty = scoring_weights.get("low_balance_penalty", 80)
        base_score -= balance_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Low Average Balance",
            condition_met=f"Average balance: {avg_balance:.2f} < 5,000",
            adjustment=-balance_penalty,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 3: Overdraft Usage Penalty
    overdraft_frequency = bank_features.get("overdraft_frequency", 0)
    if overdraft_frequency > 0.1:  # More than 10% of time overdrawn
        overdraft_penalty = scoring_weights.get("overdraft_penalty", 120)
        base_score -= overdraft_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Frequent Overdraft Usage",
            condition_met=f"Overdraft frequency: {overdraft_frequency:.2f} > 0.1",
            adjustment=-overdraft_penalty,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 4: Debt Service Ratio
    debt_service_ratio = bank_features.get("debt_service_ratio", 0)
    if debt_service_ratio > 0.4:  # More than 40% income to debt
        debt_penalty = scoring_weights.get("high_debt_penalty", 100)
        base_score -= debt_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Debt Service Ratio",
            condition_met=f"Debt service ratio: {debt_service_ratio:.2f} > 0.4",
            adjustment=-debt_penalty,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 5: Emergency Fund Coverage
    emergency_fund_months = bank_features.get("emergency_fund_months", 0)
    if emergency_fund_months >= 3:  # 3+ months coverage
        emergency_bonus = scoring_weights.get("emergency_fund_bonus", 80)
        base_score += emergency_bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Good Emergency Fund Coverage",
            condition_met=f"Emergency fund: {emergency_fund_months:.1f} months >= 3",
            adjustment=emergency_bonus,
            new_score_after_adjustment=base_score
        ))
    elif emergency_fund_months < 1:  # Less than 1 month
        emergency_penalty = scoring_weights.get("low_emergency_fund_penalty", 60)
        base_score -= emergency_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Low Emergency Fund Coverage",
            condition_met=f"Emergency fund: {emergency_fund_months:.1f} months < 1",
            adjustment=-emergency_penalty,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 6: Savings Rate
    savings_rate = bank_features.get("savings_rate", 0)
    if savings_rate > 0.15:  # More than 15% savings rate
        savings_bonus = scoring_weights.get("high_savings_bonus", 70)
        base_score += savings_bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Savings Rate",
            condition_met=f"Savings rate: {savings_rate:.2f} > 0.15",
            adjustment=savings_bonus,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 7: Anomalies Penalty
    if anomalies_detected:
        anomaly_penalty = len(anomalies_detected) * scoring_weights.get("anomaly_penalty", 25)
        base_score -= anomaly_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Transaction Anomalies",
            condition_met=f"{len(anomalies_detected)} anomalies detected",
            adjustment=-anomaly_penalty,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 8: Income Volatility
    income_volatility = bank_features.get("income_volatility", 0)
    if income_volatility > 0.5:  # High volatility
        volatility_penalty = scoring_weights.get("income_volatility_penalty", 50)
        base_score -= volatility_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Income Volatility",
            condition_met=f"Income volatility: {income_volatility:.2f} > 0.5",
            adjustment=-volatility_penalty,
            new_score_after_adjustment=base_score
        ))
    
    # Clamp score to 0-1000 range
    final_score = max(0, min(1000, base_score))
    
    return {
        "bank_behavioral_score": final_score,
        "score_components": {
            "income_consistency_impact": income_score - 100,
            "balance_impact": 0,  # Calculated above in rules
            "overdraft_impact": 0,  # Calculated above in rules  
            "debt_impact": 0,  # Calculated above in rules
            "savings_impact": 0,  # Calculated above in rules
            "anomalies_impact": -len(anomalies_detected) * scoring_weights.get("anomaly_penalty", 25) if anomalies_detected else 0
        },
        "rule_engine_breakdown": rule_engine_breakdown,
        "risk_level": _get_risk_level(final_score)
    }

def _get_risk_level(score: float) -> str:
    """Determine risk level based on score"""
    if score >= 800:
        return "Very Low Risk"
    elif score >= 650:
        return "Low Risk"
    elif score >= 500:
        return "Medium Risk"
    elif score >= 350:
        return "High Risk"
    else:
        return "Very High Risk"
