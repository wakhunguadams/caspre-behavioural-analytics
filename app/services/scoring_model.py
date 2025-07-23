from typing import Dict, Any, List
import pandas as pd
import numpy as np
import xgboost as xgb
import shap # For explainable AI
from app.schemas.responses import RuleBreakdown
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
    "savings_rate"
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