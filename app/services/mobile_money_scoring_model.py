from typing import Dict, Any, List
import pandas as pd
import numpy as np
from app.schemas.response import RuleBreakdown
from app.utils.tenant_config import get_tenant_config

async def calculate_mobile_money_behavioral_score(
    customer_id: str,
    mobile_features: Dict[str, Any],
    anomalies_detected: List[Any],
    company_id: str
) -> Dict[str, Any]:
    """
    Calculates the behavioral score specifically for mobile money transaction data.
    Score range: 0-1000
    """
    
    # Initialize base score
    base_score = 500
    
    tenant_config = await get_tenant_config(company_id)
    scoring_weights = tenant_config.get("mobile_money_scoring_weights", {})
    rule_engine_breakdown: List[RuleBreakdown] = []
    
    # Mobile Money-specific scoring rules
    
    # Rule 1: Daily Spending Consistency
    daily_spending_mean = mobile_features.get("daily_spending_mean", 0)
    if daily_spending_mean > 0 and daily_spending_mean < 10000:  # Reasonable daily spending
        consistency_bonus = scoring_weights.get("consistent_spending_bonus", 30)
        base_score += consistency_bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Consistent Daily Spending",
            condition_met=f"Daily spending mean: {daily_spending_mean:.2f} within reasonable range",
            adjustment=consistency_bonus,
            new_score_after_adjustment=base_score
        ))
    elif daily_spending_mean > 20000:  # Very high spending
        high_spending_penalty = scoring_weights.get("high_spending_penalty", 60)
        base_score -= high_spending_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Daily Spending",
            condition_met=f"Daily spending mean: {daily_spending_mean:.2f} > 20,000",
            adjustment=-high_spending_penalty,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 2: Mobile Loan Dependency
    loan_repayment_ratio = mobile_features.get("loan_repayment_ratio", 0)
    if loan_repayment_ratio > 0.3:  # More than 30% of income goes to mobile loans
        loan_dependency_penalty = scoring_weights.get("high_loan_dependency_penalty", 80)
        base_score -= loan_dependency_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Mobile Loan Dependency",
            condition_met=f"Loan repayment ratio: {loan_repayment_ratio:.2f} > 0.3",
            adjustment=-loan_dependency_penalty,
            new_score_after_adjustment=base_score
        ))
    elif loan_repayment_ratio > 0 and loan_repayment_ratio <= 0.1:  # Moderate, manageable loans
        manageable_loan_bonus = scoring_weights.get("manageable_loan_bonus", 20)
        base_score += manageable_loan_bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Manageable Mobile Loan Usage",
            condition_met=f"Loan repayment ratio: {loan_repayment_ratio:.2f} <= 0.1",
            adjustment=manageable_loan_bonus,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 3: Remittance Activity (Positive indicator of financial connectivity)
    remittance_frequency = mobile_features.get("remittance_frequency", 0)
    if remittance_frequency > 5:  # Regular remittance activity
        remittance_bonus = scoring_weights.get("active_remittance_bonus", 40)
        base_score += remittance_bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Active Remittance Activity",
            condition_met=f"Remittance frequency: {remittance_frequency} > 5",
            adjustment=remittance_bonus,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 4: Transaction Pattern Anomalies
    if anomalies_detected:
        anomaly_penalty = len(anomalies_detected) * scoring_weights.get("anomaly_penalty", 20)
        base_score -= anomaly_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Mobile Money Anomalies",
            condition_met=f"{len(anomalies_detected)} anomalies detected",
            adjustment=-anomaly_penalty,
            new_score_after_adjustment=base_score
        ))
    
    # Rule 5: Financial Inclusion Score (Having mobile money shows digital financial inclusion)
    inclusion_bonus = scoring_weights.get("digital_inclusion_bonus", 50)
    base_score += inclusion_bonus
    rule_engine_breakdown.append(RuleBreakdown(
        rule_name="Digital Financial Inclusion",
        condition_met="Active mobile money usage indicates digital financial inclusion",
        adjustment=inclusion_bonus,
        new_score_after_adjustment=base_score
    ))
    
    # Rule 6: P2P Transfer Activity (Social financial networks)
    # This would need to be calculated from transaction patterns in the actual implementation
    # For now, we'll use a placeholder based on remittance frequency as a proxy
    if remittance_frequency > 10:  # Very active P2P
        social_network_bonus = scoring_weights.get("strong_social_network_bonus", 25)
        base_score += social_network_bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Strong Social Financial Network",
            condition_met=f"High P2P activity indicated by remittance frequency: {remittance_frequency}",
            adjustment=social_network_bonus,
            new_score_after_adjustment=base_score
        ))
    
    # Clamp score to 0-1000 range
    final_score = max(0, min(1000, base_score))
    
    return {
        "mobile_money_behavioral_score": final_score,
        "score_components": {
            "spending_consistency_impact": consistency_bonus if "consistency_bonus" in locals() else (-high_spending_penalty if "high_spending_penalty" in locals() else 0),
            "loan_dependency_impact": -loan_dependency_penalty if "loan_dependency_penalty" in locals() else (manageable_loan_bonus if "manageable_loan_bonus" in locals() else 0),
            "remittance_impact": remittance_bonus if "remittance_bonus" in locals() else 0,
            "anomalies_impact": -len(anomalies_detected) * scoring_weights.get("anomaly_penalty", 20) if anomalies_detected else 0,
            "inclusion_impact": inclusion_bonus,
            "social_network_impact": social_network_bonus if "social_network_bonus" in locals() else 0
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
