from typing import Dict, Any, List
import pandas as pd
import numpy as np
from app.schemas.response import RuleBreakdown
from app.utils.tenant_config import get_tenant_config

async def calculate_crb_behavioral_score(
    customer_id: str,
    crb_data: Dict[str, Any],
    company_id: str
) -> Dict[str, Any]:
    """
    Calculates the behavioral score specifically for CRB data.
    Score range: 0-1000
    """
    
    # Initialize base score
    base_score = 500
    
    tenant_config = await get_tenant_config(company_id)
    scoring_weights = tenant_config.get("crb_scoring_weights", {})
    rule_engine_breakdown: List[RuleBreakdown] = []
    
    # CRB-specific scoring rules
    
    # Rule 1: Credit History Length
    credit_history_length = crb_data.get("credit_history_months", 0)
    if credit_history_length >= 24:  # 2+ years
        history_bonus = scoring_weights.get("long_credit_history_bonus", 50)
        base_score += history_bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Long Credit History",
            condition_met=f"Credit History Length ({credit_history_length} months) >= 24.",
            adjustment=history_bonus,
            new_score_after_adjustment=base_score
        ))

    # Rule 2: Payment Performance
    payment_performance = crb_data.get("payment_performance_score", 0)
    payment_score_adjustment = (payment_performance / 100.0) * 200 - 100
    base_score += payment_score_adjustment
    rule_engine_breakdown.append(RuleBreakdown(
        rule_name="Payment Performance",
        condition_met=f"Payment performance score: {payment_performance}",
        adjustment=payment_score_adjustment,
        new_score_after_adjustment=base_score
    ))

    # Rule 3: Credit Utilization
    credit_utilization = crb_data.get("credit_utilization_ratio", 0)
    if credit_utilization > 75:
        utilization_penalty = scoring_weights.get("high_credit_utilization_penalty", 70)
        base_score -= utilization_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Credit Utilization",
            condition_met=f"Credit Utilization Ratio ({credit_utilization}%) > 75%.",
            adjustment=-utilization_penalty,
            new_score_after_adjustment=base_score
        ))

    # Rule 4: Recent Late Payments
    recent_late_payments = crb_data.get("recent_late_payments", 0)
    if recent_late_payments > 0:
        late_payment_penalty = recent_late_payments * scoring_weights.get("late_payment_penalty_per_instance", 20)
        base_score -= late_payment_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Recent Late Payments",
            condition_met=f"{recent_late_payments} recent late payments",
            adjustment=-late_payment_penalty,
            new_score_after_adjustment=base_score
        ))

    # Rule 5: Credit Inquiries
    credit_inquiries = crb_data.get("credit_inquiries", 0)
    if credit_inquiries > 5:
        inquiry_penalty = scoring_weights.get("frequent_inquiries_penalty", 50)
        base_score -= inquiry_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Frequent Credit Inquiries",
            condition_met=f"{credit_inquiries} credit inquiries",
            adjustment=-inquiry_penalty,
            new_score_after_adjustment=base_score
        ))

    # Clamp score to 0-1000 range
    final_score = max(0, min(1000, base_score))

    return {
        "crb_behavioral_score": final_score,
        "score_components": {
            "history_impact": history_bonus if "history_bonus" in locals() else 0,
            "payment_impact": payment_score_adjustment,
            "utilization_impact": -utilization_penalty if "utilization_penalty" in locals() else 0,
            "late_payments_impact": -late_payment_penalty if "late_payment_penalty" in locals() else 0,
            "inquiries_impact": -inquiry_penalty if "inquiry_penalty" in locals() else 0
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





