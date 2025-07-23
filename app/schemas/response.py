from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class Transaction(BaseModel):
    """Represents a single extracted transaction from a bank statement."""
    date: str
    description: str
    amount: float
    type: str # 'debit' or 'credit'
    category: Optional[str] = None # Added during feature engineering
    balance_after: Optional[float] = None
    original_currency: Optional[str] = None # For multi-currency statements

class KeyMetric(BaseModel):
    """Represents a single derived financial health indicator."""
    name: str
    value: Any
    unit: Optional[str] = None
    description: Optional[str] = None

class Anomaly(BaseModel):
    """Represents a detected anomaly in the bank statement."""
    type: str
    description: str
    transaction: Optional[Dict[str, Any]] = None # The transaction that caused the anomaly
    reason: Optional[str] = None

class RuleBreakdown(BaseModel):
    """Details about a tenant-specific rule that was triggered."""
    rule_name: str
    condition_met: str
    adjustment: float
    new_score_after_adjustment: Optional[float] = None

class BehavioralAnalyticsResult(BaseModel):
    """Comprehensive schema for the final behavioral analytics result."""
    company_id: str
    customer_id: str
    job_id: str
    status: str = Field(..., description="Status of the analysis: 'completed', 'failed', etc.")
    
    # Core outputs
    behavioral_score: float = Field(..., description="Overall behavioral score (e.g., 0-1000).")
    score_explanation: Dict[str, Any] = Field(..., description="Explainable AI factors contributing to the score (e.g., SHAP values, positive/negative drivers).")
    analysis_summary: str = Field(..., description="LLM-generated human-readable narrative summary of financial behavior.")
    
    # Detailed data
    key_metrics: List[KeyMetric] = Field(..., description="List of derived financial health indicators.")
    categorized_transactions: List[Transaction] = Field(..., description="List of all categorized transactions.")
    anomalies_detected: List[Anomaly] = Field([], description="List of detected suspicious transactions or patterns.")
    rule_engine_breakdown: List[RuleBreakdown] = Field([], description="Details on which tenant-specific rules were applied and their impact.")
    
    # Metadata
    localization_details: Dict[str, Any] = Field(..., description="Details about language detected, currency, and region.")
    processed_at: str # ISO format datetime of completion
    
    # Error information if status is 'failed'
    error_message: Optional[str] = None
    detail: Optional[str] = None