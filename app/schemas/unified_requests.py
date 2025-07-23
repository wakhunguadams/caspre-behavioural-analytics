from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.schemas.response import Transaction

class CRBDataInput(BaseModel):
    """Schema for Credit Reference Bureau data input"""
    credit_history_months: int = Field(..., description="Length of credit history in months")
    payment_performance_score: float = Field(..., ge=0, le=100, description="Payment performance score (0-100)")
    recent_late_payments: int = Field(default=0, ge=0, description="Number of recent late payments")
    credit_utilization_ratio: float = Field(..., ge=0, le=100, description="Credit utilization percentage")
    credit_types: Dict[str, Any] = Field(default_factory=dict, description="Types of credit products")
    credit_inquiries: int = Field(default=0, ge=0, description="Number of recent credit inquiries")
    accounts: List[Dict[str, Any]] = Field(default_factory=list, description="List of credit accounts")

class UnifiedBehavioralAnalyticsRequest(BaseModel):
    """Request schema for unified behavioral analytics processing"""
    company_id: str = Field(..., description="Tenant/company identifier")
    customer_id: str = Field(..., description="Customer identifier")
    bank_transactions: Optional[List[Transaction]] = Field(default=None, description="Bank transaction data")
    crb_data: Optional[CRBDataInput] = Field(default=None, description="Credit Reference Bureau data")
    mobile_money_transactions: Optional[List[Transaction]] = Field(default=None, description="Mobile money transaction data")
    data_sources: List[str] = Field(..., description="List of provided data sources", example=["bank_transactions", "crb_data", "mobile_money"])
    callback_url: Optional[str] = Field(default=None, description="Optional callback URL for notifications")

class UnifiedBehavioralAnalyticsResponse(BaseModel):
    """Response schema for unified behavioral analytics"""
    company_id: str
    customer_id: str
    status: str = Field(..., description="Processing status")
    behavioral_score: float = Field(..., description="Overall behavioral score (0-1000)")
    score_explanation: Dict[str, float] = Field(..., description="SHAP values explaining score factors")
    analysis_summary: str = Field(..., description="Human-readable analysis summary")
    
    # Data source specific analysis
    data_source_analysis: Dict[str, Any] = Field(..., description="Analysis results by data source")
    data_completeness: Dict[str, Any] = Field(..., description="Data availability and completeness metrics")
    
    # Aggregated results
    key_metrics: List[Dict[str, Any]] = Field(..., description="Key financial metrics across all sources")
    categorized_transactions: List[Dict[str, Any]] = Field(..., description="All categorized transactions")
    anomalies_detected: List[Dict[str, Any]] = Field(..., description="All detected anomalies")
    rule_engine_breakdown: List[Dict[str, Any]] = Field(..., description="Applied scoring rules and adjustments")
    
    # Metadata
    processed_at: str = Field(..., description="Processing timestamp")
    processing_time_ms: Optional[float] = Field(default=None, description="Processing time in milliseconds")

class DataUploadRequest(BaseModel):
    """Request schema for uploading structured data directly (without file processing)"""
    callback_url: Optional[str] = Field(default=None, description="Optional callback URL for notifications")
