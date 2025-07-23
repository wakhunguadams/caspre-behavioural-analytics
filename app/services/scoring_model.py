from typing import Dict, Any, List
import pandas as pd
import numpy as np
import xgboost as xgb
import shap # For explainable AI
from app.schemas.response import RuleBreakdown
from app.utils.tenant_config import get_tenant_config

# Placeholder for a trained model. In a real system, this would be loaded from
# a model registry (e.g., MLflow, S3/GCS, or local file system if part of deployment).
# For demonstration, we'll create a dummy model.
_dummy_model: xgb.XGBRegressor = None
_feature_names: List[str] = [
    "avg_monthly_income",
    "income_consistency", 
    "total_spending",
    "spending_to_income_ratio",
    "loan_repayments",
    "avg_daily_balance",
    "min_balance",
    "max_balance",
    "savings_rate",
    # CRB features
    "crb_credit_history_length",
    "crb_payment_performance", 
    "crb_credit_utilization",
    "crb_num_credit_types",
    # Mobile money features
    "daily_spending_mean",
    "loan_repayment_ratio",
    "remittance_frequency",
    # Cross-source features
    "data_completeness_score",
    "spending_consistency",
    "risk_diversification_score",
    # Enhanced bank features
    "income_volatility",
    "overdraft_frequency",
    "debt_service_ratio",
    "emergency_fund_months",
    "cash_flow_variance"
]

def _initialize_dummy_model():
    """Initializes a dummy XGBoost model for demonstration."""
    global _dummy_model
    if _dummy_model is None:
        # Create a simple, pre-trained dummy model
        _dummy_model = xgb.XGBRegressor(
            objective='reg:squarederror',
            n_estimators=10,
            random_state=42
        )
        # Train it on some random data to make it 'trained'
        X_dummy = pd.DataFrame(np.random.rand(100, len(_feature_names)), columns=_feature_names)
        y_dummy = np.random.rand(100) * 1000 # Scores between 0-1000
        _dummy_model.fit(X_dummy, y_dummy)
        print("Dummy behavioral scoring model initialized.")

async def calculate_behavioral_score(
    customer_id: str,
    all_features: Dict[str, Any],
    anomalies_detected: List[Any], # List of Anomaly Pydantic models
    company_id: str
) -> Dict[str, Any]:
    """
    Calculates the behavioral score for a customer and provides explanations.
    """
    _initialize_dummy_model()

    # Convert features to a format the model expects
    # Ensure all expected features are present, fill with 0 or a sensible default if missing
    feature_vector = pd.DataFrame([
        {feat: all_features.get(feat, 0) for feat in _feature_names}
    ])

    # Predict the score
    # Ensure all features needed by the model are in feature_vector
    # If the model was trained on different features, this will cause an error
    score = float(_dummy_model.predict(feature_vector)[0])
    
    # Apply tenant-specific rule adjustments
    tenant_config = await get_tenant_config(company_id)
    behavioral_scoring_weights = tenant_config.get("behavioral_scoring_weights", {})
    rule_engine_breakdown: List[RuleBreakdown] = []

    # Example Rule 1: Penalty for high spending to income ratio
    spending_to_income_ratio = all_features.get("spending_to_income_ratio", 0)
    if spending_to_income_ratio > 0.8: # If more than 80% of income is spent
        penalty = behavioral_scoring_weights.get("high_spending_penalty", 50)
        original_score = score
        score -= penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Spending to Income Ratio",
            condition_met=f"Spending to Income Ratio ({spending_to_income_ratio:.2f}) exceeded 0.8.",
            adjustment=-penalty,
            new_score_after_adjustment=score
        ))

    # Example Rule 2: Bonus for high savings rate
    savings_rate = all_features.get("savings_rate", 0)
    if savings_rate > 0.1: # If savings rate is over 10%
        bonus = behavioral_scoring_weights.get("high_savings_bonus", 20)
        original_score = score
        score += bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Savings Rate",
            condition_met=f"Savings Rate ({savings_rate:.2f}) exceeded 0.1.",
            adjustment=+bonus,
            new_score_after_adjustment=score
        ))

    # Example Rule 3: Penalty for detected anomalies
    if anomalies_detected:
        anomaly_penalty_per_anomaly = behavioral_scoring_weights.get("anomaly_penalty_per_anomaly", 20)
        total_anomaly_penalty = len(anomalies_detected) * anomaly_penalty_per_anomaly
        original_score = score
        score -= total_anomaly_penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Detected Anomalies",
            condition_met=f"{len(anomalies_detected)} anomalies detected.",
            adjustment=-total_anomaly_penalty,
            new_score_after_adjustment=score
        ))
    
    # CRB-specific rules
    crb_payment_performance = all_features.get("crb_payment_performance", 0)
    if crb_payment_performance > 0:  # Only apply if CRB data is available
        # Rule 4: Bonus for excellent CRB payment performance
        if crb_payment_performance >= 80:
            bonus = behavioral_scoring_weights.get("excellent_crb_performance_bonus", 40)
            score += bonus
            rule_engine_breakdown.append(RuleBreakdown(
                rule_name="Excellent CRB Payment Performance",
                condition_met=f"CRB Payment Performance ({crb_payment_performance}) >= 80.",
                adjustment=bonus,
                new_score_after_adjustment=score
            ))
        # Rule 5: Penalty for poor CRB payment performance
        elif crb_payment_performance < 40:
            penalty = behavioral_scoring_weights.get("poor_crb_performance_penalty", 60)
            score -= penalty
            rule_engine_breakdown.append(RuleBreakdown(
                rule_name="Poor CRB Payment Performance",
                condition_met=f"CRB Payment Performance ({crb_payment_performance}) < 40.",
                adjustment=-penalty,
                new_score_after_adjustment=score
            ))
    
    # Rule 6: Bonus for long credit history
    credit_history_length = all_features.get("crb_credit_history_length", 0)
    if credit_history_length >= 24:  # 2+ years of credit history
        bonus = behavioral_scoring_weights.get("long_credit_history_bonus", 25)
        score += bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Long Credit History",
            condition_met=f"Credit History Length ({credit_history_length} months) >= 24.",
            adjustment=bonus,
            new_score_after_adjustment=score
        ))
    
    # Rule 7: Penalty for high credit utilization
    credit_utilization = all_features.get("crb_credit_utilization", 0)
    if credit_utilization > 75:
        penalty = behavioral_scoring_weights.get("high_credit_utilization_penalty", 35)
        score -= penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Credit Utilization",
            condition_met=f"Credit Utilization ({credit_utilization}%) > 75%.",
            adjustment=-penalty,
            new_score_after_adjustment=score
        ))
    
    # Mobile money specific rules
    # Rule 8: Penalty for high mobile loan dependency
    mobile_loan_ratio = all_features.get("loan_repayment_ratio", 0)
    if mobile_loan_ratio > 0.3:  # More than 30% of income goes to mobile loans
        penalty = behavioral_scoring_weights.get("high_mobile_loan_dependency_penalty", 45)
        score -= penalty
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="High Mobile Loan Dependency",
            condition_met=f"Mobile Loan Repayment Ratio ({mobile_loan_ratio:.2f}) > 0.3.",
            adjustment=-penalty,
            new_score_after_adjustment=score
        ))
    
    # Rule 9: Bonus for good data completeness
    data_completeness = all_features.get("data_completeness_score", 0)
    if data_completeness >= 0.67:  # At least 2 out of 3 data sources
        bonus = behavioral_scoring_weights.get("good_data_completeness_bonus", 15)
        score += bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Good Data Completeness",
            condition_met=f"Data Completeness Score ({data_completeness:.2f}) >= 0.67.",
            adjustment=bonus,
            new_score_after_adjustment=score
        ))
    
    # Rule 10: Bonus for consistent spending patterns across sources
    spending_consistency = all_features.get("spending_consistency", 0)
    if spending_consistency > 0.8:  # High consistency between bank and mobile money
        bonus = behavioral_scoring_weights.get("spending_consistency_bonus", 20)
        score += bonus
        rule_engine_breakdown.append(RuleBreakdown(
            rule_name="Consistent Spending Patterns",
            condition_met=f"Spending Consistency ({spending_consistency:.2f}) > 0.8.",
            adjustment=bonus,
            new_score_after_adjustment=score
        ))

    # Clamp score to a reasonable range (e.g., 0-1000)
    score = max(0, min(1000, score))

    # Generate SHAP explanation (requires explainer to be fitted to the model)
    explainer = shap.Explainer(_dummy_model)
    shap_values = explainer(feature_vector)
    
    # Extract SHAP values for the first (and only) prediction
    feature_impact = {
        _feature_names[i]: float(shap_values.values[0][i])
        for i in range(len(_feature_names))
    }
    
    # Sort features by absolute impact for easier understanding
    sorted_impact = dict(sorted(feature_impact.items(), key=lambda item: abs(item[1]), reverse=True))

    return {
        "behavioral_score": score,
        "score_explanation": sorted_impact,
        "rule_engine_breakdown": rule_engine_breakdown
    }