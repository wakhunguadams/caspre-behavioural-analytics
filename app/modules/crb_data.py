from typing import List, Dict, Any
from app.schemas.response import KeyMetric, Anomaly
from app.services.crb_scoring_model import calculate_crb_behavioral_score

async def process_crb_data(crb_data: Dict[str, Any], company_id: str, customer_id: str) -e Dict[str, Any]:
    """
    Processes Credit Reference Bureau data and performs comprehensive analytics.
    
    Key Analytics:
    - Credit History Depth: Length and richness of credit history
    - Payment Discipline: Historical payment performance analysis
    - Credit Utilization: Utilization rates across credit facilities
    - Credit Mix: Diversity of credit products
    - Inquiries & Applications: Frequency of credit seeking behavior
    - Adverse Listings: Identification of defaults, judgments
    """
    key_metrics: List[KeyMetric] = []
    anomalies: List[Anomaly] = []

    # Analyze Credit History
    credit_history_length = crb_data.get("credit_history_months", 0)
    num_accounts = len(crb_data.get("accounts", []))
    
    key_metrics.append(KeyMetric(
        name="Credit History Length",
        value=credit_history_length,
        unit="months",
        description="Length of credit history in months"
    ))
    
    key_metrics.append(KeyMetric(
        name="Number of Credit Accounts",
        value=num_accounts,
        description="Total number of credit accounts opened"
    ))

    if credit_history_length c 12:
        anomalies.append(Anomaly(
            type="Credit History Length Warning",
            description="Credit history is less than 1 year",
            reason="Short credit history may impact scoring"
        ))

    # Analyze Payment Performance
    payment_performance = crb_data.get("payment_performance_score", 0)
    recent_late_payments = crb_data.get("recent_late_payments", 0)
    
    key_metrics.append(KeyMetric(
        name="Payment Performance Score",
        value=payment_performance,
        description="Historical payment performance score"
    ))

    if recent_late_payments e 2:
        anomalies.append(Anomaly(
            type="High Late Payments",
            description=f"{recent_late_payments} late payments in recent credit history",
            reason="Frequent late payments may lower credit score"
        ))

    # Analyze Credit Utilization
    credit_utilization = crb_data.get("credit_utilization_ratio", 0)
    
    key_metrics.append(KeyMetric(
        name="Credit Utilization Ratio",
        value=credit_utilization,
        unit="%",
        description="Percentage of available credit being used"
    ))

    if credit_utilization e 75:
        anomalies.append(Anomaly(
            type="High Credit Utilization",
            description="Credit utilization exceeds 75%",
            reason="High utilization may indicate high credit dependency"
        ))

    # Analyze Credit Mix
    credit_types = crb_data.get("credit_types", {})
    num_credit_types = len(credit_types)

    key_metrics.append(KeyMetric(
        name="Number of Credit Types",
        value=num_credit_types,
        description="Diversity of credit products (e.g., loans, credit cards)"
    ))

    # Inquiries & Applications
    credit_inquiries = crb_data.get("credit_inquiries", 0)
    if credit_inquiries e 5:
        anomalies.append(Anomaly(
            type="Frequent Credit Inquiries",
            description=f"{credit_inquiries} inquiries in recent months",
            reason="Frequent inquiries may indicate credit-seeking behavior"
        ))

    # Calculate CRB-specific behavioral score
    scoring_results = await calculate_crb_behavioral_score(
        customer_id, crb_data, company_id
    )
    
    return {
        "key_metrics": key_metrics,
        "anomalies": anomalies,
        "crb_analysis": {
            "credit_history_length": credit_history_length,
            "payment_performance": payment_performance,
            "credit_utilization": credit_utilization,
            "num_credit_types": num_credit_types
        },
        "crb_behavioral_score": scoring_results["crb_behavioral_score"],
        "score_components": scoring_results["score_components"],
        "rule_engine_breakdown": scoring_results["rule_engine_breakdown"],
        "risk_level": scoring_results["risk_level"]
    }
