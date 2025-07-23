import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from app.schemas.response import Transaction, KeyMetric, Anomaly, RuleBreakdown
from app.modules.bank_transactions import process_bank_transactions
from app.modules.crb_data import process_crb_data
from app.modules.mobile_money_transactions import process_mobile_money_transactions
from app.services.scoring_model import calculate_behavioral_score
from app.utils.tenant_config import get_tenant_config
import json

class UnifiedBehavioralProcessor:
    """
    Unified processor for analyzing bank transactions, CRB data, and mobile money transactions
    to generate comprehensive behavioral analytics and scoring.
    """
    
    def __init__(self):
        self.supported_data_types = ["bank_transactions", "crb_data", "mobile_money"]
    
    async def process_unified_data(
        self,
        company_id: str,
        customer_id: str,
        data_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main processing function that handles different data types and generates unified analytics.
        
        Args:
            company_id: Tenant/company identifier
            customer_id: Customer identifier
            data_payload: Dictionary containing different data types:
                {
                    "bank_transactions": [...],  # List of Transaction objects or dicts
                    "crb_data": {...},          # CRB data dictionary
                    "mobile_money": [...],      # List of mobile money transactions
                    "data_sources": [...]       # List indicating which sources are provided
                }
        
        Returns:
            Comprehensive behavioral analytics result
        """
        
        # Initialize results structure
        unified_results = {
            "all_features": {},
            "key_metrics": [],
            "categorized_transactions": [],
            "anomalies_detected": [],
            "data_source_analysis": {},
            "behavioral_score": 0,
            "score_explanation": {},
            "rule_engine_breakdown": [],
            "analysis_summary": "",
            "data_completeness": {}
        }
        
        # Track which data sources were provided
        provided_sources = data_payload.get("data_sources", [])
        data_completeness = {}
        
        # Process Bank Transactions
        if "bank_transactions" in data_payload and data_payload["bank_transactions"]:
            bank_data = await self._process_bank_data(
                data_payload["bank_transactions"], company_id, customer_id
            )
            unified_results["data_source_analysis"]["bank_transactions"] = bank_data
            unified_results["all_features"].update(bank_data["all_features"])
            unified_results["key_metrics"].extend(bank_data["key_metrics"])
            unified_results["categorized_transactions"].extend(bank_data["categorized_transactions"])
            unified_results["anomalies_detected"].extend(bank_data["anomalies_detected"])
            data_completeness["bank_transactions"] = {
                "available": True,
                "transaction_count": len(bank_data["categorized_transactions"]),
                "date_range": self._get_date_range(bank_data["categorized_transactions"])
            }
        else:
            data_completeness["bank_transactions"] = {"available": False}
        
        # Process CRB Data
        if "crb_data" in data_payload and data_payload["crb_data"]:
            crb_results = await process_crb_data(
                data_payload["crb_data"], company_id, customer_id
            )
            unified_results["data_source_analysis"]["crb_data"] = crb_results
            unified_results["key_metrics"].extend(crb_results["key_metrics"])
            unified_results["anomalies_detected"].extend(crb_results["anomalies_detected"])
            
            # Add CRB-specific features to unified features
            if "crb_analysis" in crb_results:
                for key, value in crb_results["crb_analysis"].items():
                    unified_results["all_features"][f"crb_{key}"] = value
            
            data_completeness["crb_data"] = {
                "available": True,
                "credit_history_months": crb_results.get("crb_analysis", {}).get("credit_history_length", 0),
                "accounts_count": len(data_payload["crb_data"].get("accounts", []))
            }
        else:
            data_completeness["crb_data"] = {"available": False}
        
        # Process Mobile Money Transactions
        if "mobile_money" in data_payload and data_payload["mobile_money"]:
            mobile_data = await self._process_mobile_money_data(
                data_payload["mobile_money"], company_id, customer_id
            )
            unified_results["data_source_analysis"]["mobile_money"] = mobile_data
            unified_results["all_features"].update(mobile_data["all_features"])
            unified_results["key_metrics"].extend(mobile_data["key_metrics"])
            unified_results["categorized_transactions"].extend(mobile_data["categorized_transactions"])
            unified_results["anomalies_detected"].extend(mobile_data["anomalies_detected"])
            
            data_completeness["mobile_money"] = {
                "available": True,
                "transaction_count": len(mobile_data["categorized_transactions"]),
                "date_range": self._get_date_range(mobile_data["categorized_transactions"])
            }
        else:
            data_completeness["mobile_money"] = {"available": False}
        
        # Generate cross-source insights
        cross_source_metrics = await self._generate_cross_source_insights(
            unified_results, data_completeness, company_id
        )
        unified_results["key_metrics"].extend(cross_source_metrics["metrics"])
        unified_results["anomalies_detected"].extend(cross_source_metrics["anomalies"])
        unified_results["all_features"].update(cross_source_metrics["features"])
        
        # Calculate unified behavioral score
        scoring_results = await calculate_behavioral_score(
            customer_id, unified_results["all_features"], 
            unified_results["anomalies_detected"], company_id
        )
        
        unified_results["behavioral_score"] = scoring_results["behavioral_score"]
        unified_results["score_explanation"] = scoring_results["score_explanation"]
        unified_results["rule_engine_breakdown"] = scoring_results["rule_engine_breakdown"]
        unified_results["data_completeness"] = data_completeness
        
        # Generate comprehensive analysis summary
        unified_results["analysis_summary"] = await self._generate_unified_summary(
            unified_results, company_id, customer_id
        )
        
        return unified_results
    
    async def _process_bank_data(self, bank_transactions: List[Union[Dict, Transaction]], 
                                company_id: str, customer_id: str) -> Dict[str, Any]:
        """Process bank transaction data"""
        # Convert to Transaction objects if needed
        if bank_transactions and isinstance(bank_transactions[0], dict):
            transactions = [Transaction(**tx) for tx in bank_transactions]
        else:
            transactions = bank_transactions
        
        return await process_bank_transactions(transactions, company_id, customer_id)
    
    async def _process_mobile_money_data(self, mobile_transactions: List[Union[Dict, Transaction]], 
                                        company_id: str, customer_id: str) -> Dict[str, Any]:
        """Process mobile money transaction data"""
        # Convert to Transaction objects if needed
        if mobile_transactions and isinstance(mobile_transactions[0], dict):
            transactions = [Transaction(**tx) for tx in mobile_transactions]
        else:
            transactions = mobile_transactions
        
        return await process_mobile_money_transactions(transactions, company_id, customer_id)
    
    def _get_date_range(self, transactions: List[Dict]) -> Dict[str, str]:
        """Extract date range from transactions"""
        if not transactions:
            return {"start": None, "end": None}
        
        dates = [tx.get("date") for tx in transactions if tx.get("date")]
        if not dates:
            return {"start": None, "end": None}
        
        return {
            "start": min(dates),
            "end": max(dates)
        }
    
    async def _generate_cross_source_insights(self, unified_results: Dict[str, Any], 
                                            data_completeness: Dict[str, Any], 
                                            company_id: str) -> Dict[str, Any]:
        """Generate insights by combining data from multiple sources"""
        metrics = []
        anomalies = []
        features = {}
        
        tenant_config = await get_tenant_config(company_id)
        currency = tenant_config.get("currency_preference", "KES")
        
        # Data completeness score
        available_sources = sum(1 for source in data_completeness.values() if source.get("available", False))
        total_sources = len(data_completeness)
        completeness_score = available_sources / total_sources if total_sources > 0 else 0
        
        metrics.append(KeyMetric(
            name="Data Completeness Score",
            value=round(completeness_score, 2),
            description=f"Proportion of available data sources ({available_sources}/{total_sources})"
        ))
        features["data_completeness_score"] = completeness_score
        
        # Cross-validation insights
        bank_available = data_completeness.get("bank_transactions", {}).get("available", False)
        mobile_available = data_completeness.get("mobile_money", {}).get("available", False)
        crb_available = data_completeness.get("crb_data", {}).get("available", False)
        
        if bank_available and mobile_available:
            # Analyze consistency between bank and mobile money data
            bank_features = unified_results["data_source_analysis"].get("bank_transactions", {}).get("all_features", {})
            mobile_features = unified_results["data_source_analysis"].get("mobile_money", {}).get("all_features", {})
            
            # Compare spending patterns
            bank_spending = bank_features.get("total_spending", 0)
            mobile_spending = mobile_features.get("daily_spending_mean", 0) * 30  # Approximate monthly
            
            if bank_spending > 0 and mobile_spending > 0:
                spending_consistency = 1 - abs(bank_spending - mobile_spending) / max(bank_spending, mobile_spending)
                metrics.append(KeyMetric(
                    name="Bank-Mobile Spending Consistency",
                    value=round(spending_consistency, 2),
                    description="Consistency between bank and mobile money spending patterns"
                ))
                features["spending_consistency"] = spending_consistency
        
        if crb_available and (bank_available or mobile_available):
            # Cross-validate payment behavior
            crb_analysis = unified_results["data_source_analysis"].get("crb_data", {}).get("crb_analysis", {})
            payment_performance = crb_analysis.get("payment_performance", 0)
            
            # Check if transaction patterns align with CRB payment performance
            total_anomalies = len(unified_results["anomalies_detected"])
            if payment_performance < 50 and total_anomalies == 0:
                anomalies.append(Anomaly(
                    type="CRB-Transaction Mismatch",
                    description="Low CRB payment performance but no transaction anomalies detected",
                    reason="May indicate recent improvement in financial behavior or data inconsistency"
                ))
            elif payment_performance > 80 and total_anomalies > 3:
                anomalies.append(Anomaly(
                    type="CRB-Transaction Mismatch", 
                    description="High CRB payment performance but multiple transaction anomalies detected",
                    reason="May indicate recent deterioration in financial behavior"
                ))
        
        # Risk diversification analysis
        if available_sources >= 2:
            risk_diversification_score = min(1.0, available_sources / 3.0)  # Max score with all 3 sources
            metrics.append(KeyMetric(
                name="Financial Data Diversification",
                value=round(risk_diversification_score, 2),
                description="Score reflecting the breadth of financial data available for analysis"
            ))
            features["risk_diversification_score"] = risk_diversification_score
        
        return {
            "metrics": metrics,
            "anomalies": anomalies,
            "features": features
        }
    
    async def _generate_unified_summary(self, unified_results: Dict[str, Any], 
                                      company_id: str, customer_id: str) -> str:
        """Generate a comprehensive summary considering all data sources"""
        
        # Get available data sources
        available_sources = []
        data_completeness = unified_results.get("data_completeness", {})
        
        if data_completeness.get("bank_transactions", {}).get("available"):
            available_sources.append("bank transactions")
        if data_completeness.get("mobile_money", {}).get("available"):
            available_sources.append("mobile money")
        if data_completeness.get("crb_data", {}).get("available"):
            available_sources.append("credit bureau data")
        
        # Build summary components
        score = unified_results["behavioral_score"]
        total_anomalies = len(unified_results["anomalies_detected"])
        
        # Determine risk level
        if score >= 750:
            risk_level = "Low Risk"
            score_description = "excellent"
        elif score >= 600:
            risk_level = "Medium Risk"
            score_description = "good"
        elif score >= 400:
            risk_level = "Medium-High Risk"
            score_description = "fair"
        else:
            risk_level = "High Risk"
            score_description = "concerning"
        
        # Generate summary
        summary_parts = [
            f"Comprehensive Behavioral Analysis for Customer {customer_id}",
            f"Data Sources: {', '.join(available_sources).title()}",
            f"Overall Behavioral Score: {score:.1f}/1000 ({score_description})",
            f"Risk Classification: {risk_level}",
        ]
        
        if total_anomalies > 0:
            summary_parts.append(f"Anomalies Detected: {total_anomalies} patterns requiring attention")
        else:
            summary_parts.append("No significant anomalies detected in the analyzed data")
        
        # Add data-source specific insights
        tenant_config = await get_tenant_config(company_id)
        currency = tenant_config.get("currency_preference", "KES")
        
        if data_completeness.get("bank_transactions", {}).get("available"):
            bank_features = unified_results["all_features"]
            avg_income = bank_features.get("avg_monthly_income", 0)
            if avg_income > 0:
                summary_parts.append(f"Average monthly income: {currency} {avg_income:,.2f}")
        
        if data_completeness.get("crb_data", {}).get("available"):
            credit_history = unified_results["all_features"].get("crb_credit_history_length", 0)
            if credit_history > 0:
                summary_parts.append(f"Credit history: {credit_history} months")
        
        # Data completeness insight
        completeness_score = unified_results["all_features"].get("data_completeness_score", 0)
        if completeness_score == 1.0:
            summary_parts.append("Analysis based on comprehensive data from all available sources")
        elif completeness_score >= 0.67:
            summary_parts.append("Analysis based on good data coverage from multiple sources")
        else:
            summary_parts.append("Analysis limited by partial data availability - consider providing additional data sources for more accurate assessment")
        
        return ". ".join(summary_parts) + "."


# Convenience function for easy import
async def process_unified_behavioral_data(
    company_id: str,
    customer_id: str, 
    data_payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function to process unified behavioral data.
    
    Args:
        company_id: Tenant identifier
        customer_id: Customer identifier
        data_payload: Dictionary containing different data types
    
    Returns:
        Comprehensive behavioral analytics result
    """
    processor = UnifiedBehavioralProcessor()
    return await processor.process_unified_data(company_id, customer_id, data_payload)
