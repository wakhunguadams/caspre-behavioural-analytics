import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datetime import datetime, timedelta
from app.schemas.response import Transaction, KeyMetric, Anomaly
from app.services.feature_engineer import perform_feature_engineering
from app.services.bank_scoring_model import calculate_bank_behavioral_score
from app.utils.tenant_config import get_tenant_config

async def process_bank_transactions(transactions: List[Transaction], company_id: str, customer_id: str) -> Dict[str, Any]:
    """
    Processes transactions from bank statements and performs comprehensive analytics.
    
    Key Analytics:
    - Income Stability: Consistency of income deposits, source analysis, volatility
    - Spending Patterns: Categorization, frequency, discretionary vs necessities
    - Cash Flow Analysis: Net cash flow, operating patterns
    - Debt Servicing: Loan repayments, overdraft utilization
    - Liquidity & Savings: Savings rate, emergency fund estimation
    - Account Behavior: Overdraft frequency, bounced transactions
    - Fraud & Anomaly Detection: Unusual patterns, suspicious transactions
    """
    if not transactions:
        return {"all_features": {}, "key_metrics": [], "categorized_transactions": [], "anomalies_detected": []}

    # Perform base feature engineering
    base_results = await perform_feature_engineering(transactions, company_id, customer_id)
    
    # Convert to DataFrame for advanced analytics
    df = pd.DataFrame([t.model_dump() for t in transactions])
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    
    tenant_config = await get_tenant_config(company_id)
    currency = tenant_config.get("currency_preference", "KES")
    
    additional_metrics = []
    enhanced_anomalies = []
    
    # Enhanced Bank-Specific Analytics
    
    # 1. INCOME STABILITY ANALYSIS
    income_analysis = await _analyze_income_stability(df, currency)
    additional_metrics.extend(income_analysis["metrics"])
    enhanced_anomalies.extend(income_analysis["anomalies"])
    
    # 2. CASH FLOW ANALYSIS
    cashflow_analysis = await _analyze_cash_flow(df, currency)
    additional_metrics.extend(cashflow_analysis["metrics"])
    enhanced_anomalies.extend(cashflow_analysis["anomalies"])
    
    # 3. DEBT SERVICING CAPACITY
    debt_analysis = await _analyze_debt_servicing(df, currency)
    additional_metrics.extend(debt_analysis["metrics"])
    enhanced_anomalies.extend(debt_analysis["anomalies"])
    
    # 4. LIQUIDITY & SAVINGS ANALYSIS
    liquidity_analysis = await _analyze_liquidity_savings(df, currency)
    additional_metrics.extend(liquidity_analysis["metrics"])
    enhanced_anomalies.extend(liquidity_analysis["anomalies"])
    
    # 5. ACCOUNT BEHAVIOR ANALYSIS
    behavior_analysis = await _analyze_account_behavior(df, currency)
    additional_metrics.extend(behavior_analysis["metrics"])
    enhanced_anomalies.extend(behavior_analysis["anomalies"])
    
    # Combine with base results
    base_results["key_metrics"].extend(additional_metrics)
    base_results["anomalies_detected"].extend(enhanced_anomalies)
    
    # Add bank-specific features to all_features
    bank_features = {
        "income_volatility": income_analysis.get("volatility", 0),
        "overdraft_frequency": behavior_analysis.get("overdraft_frequency", 0),
        "debt_service_ratio": debt_analysis.get("debt_service_ratio", 0),
        "emergency_fund_months": liquidity_analysis.get("emergency_fund_months", 0),
        "cash_flow_variance": cashflow_analysis.get("variance", 0)
    }
    base_results["all_features"].update(bank_features)
    
    # Calculate bank-specific behavioral score
    scoring_results = await calculate_bank_behavioral_score(
        customer_id, 
        base_results["all_features"], 
        base_results["anomalies_detected"], 
        company_id
    )
    
    # Add scoring results to the response
    base_results["bank_behavioral_score"] = scoring_results["bank_behavioral_score"]
    base_results["score_components"] = scoring_results["score_components"]
    base_results["rule_engine_breakdown"] = scoring_results["rule_engine_breakdown"]
    base_results["risk_level"] = scoring_results["risk_level"]
    
    return base_results

async def _analyze_income_stability(df: pd.DataFrame, currency: str) -> Dict[str, Any]:
    """Analyzes income stability and patterns"""
    metrics = []
    anomalies = []
    
    # Identify income transactions (credits > certain threshold)
    income_df = df[(df['type'] == 'credit') & (df['amount'] > 1000)]  # Adjust threshold as needed
    
    if not income_df.empty:
        # Monthly income aggregation
        income_df.set_index('date', inplace=True)
        monthly_income = income_df.resample('M')['amount'].sum()
        
        # Income consistency metrics
        income_mean = monthly_income.mean()
        income_std = monthly_income.std()
        income_cv = income_std / income_mean if income_mean > 0 else 0  # Coefficient of variation
        
        metrics.extend([
            KeyMetric(name="Income Volatility (CV)", value=round(income_cv, 3), 
                     description="Coefficient of variation of monthly income (lower is more stable)"),
            KeyMetric(name="Average Monthly Income", value=round(income_mean, 2), unit=currency,
                     description="Average monthly income from all sources"),
            KeyMetric(name="Income Standard Deviation", value=round(income_std, 2), unit=currency,
                     description="Standard deviation of monthly income")
        ])
        
        # Detect irregular income patterns
        if income_cv > 0.5:  # High variability
            anomalies.append(Anomaly(
                type="Irregular Income Pattern",
                description=f"High income volatility detected (CV: {income_cv:.2f})",
                reason="Income varies significantly month-to-month"
            ))
    
    return {"metrics": metrics, "anomalies": anomalies, "volatility": income_cv if 'income_cv' in locals() else 0}

async def _analyze_cash_flow(df: pd.DataFrame, currency: str) -> Dict[str, Any]:
    """Analyzes cash flow patterns"""
    metrics = []
    anomalies = []
    
    # Calculate daily net cash flow
    df['net_flow'] = df.apply(lambda x: x['amount'] if x['type'] == 'credit' else -x['amount'], axis=1)
    daily_flow = df.groupby('date')['net_flow'].sum()
    
    # Cash flow metrics
    positive_days = (daily_flow > 0).sum()
    negative_days = (daily_flow < 0).sum()
    total_days = len(daily_flow)
    
    cash_flow_variance = daily_flow.var()
    avg_daily_flow = daily_flow.mean()
    
    metrics.extend([
        KeyMetric(name="Positive Cash Flow Days", value=positive_days, 
                 description="Number of days with positive cash flow"),
        KeyMetric(name="Negative Cash Flow Days", value=negative_days,
                 description="Number of days with negative cash flow"),
        KeyMetric(name="Cash Flow Ratio", value=round(positive_days/total_days, 2) if total_days > 0 else 0,
                 description="Ratio of positive to total cash flow days"),
        KeyMetric(name="Average Daily Cash Flow", value=round(avg_daily_flow, 2), unit=currency,
                 description="Average net cash flow per day")
    ])
    
    # Detect concerning cash flow patterns
    if negative_days > positive_days:
        anomalies.append(Anomaly(
            type="Negative Cash Flow Pattern",
            description="More days with negative cash flow than positive",
            reason=f"Negative days: {negative_days}, Positive days: {positive_days}"
        ))
    
    return {"metrics": metrics, "anomalies": anomalies, "variance": cash_flow_variance}

async def _analyze_debt_servicing(df: pd.DataFrame, currency: str) -> Dict[str, Any]:
    """Analyzes debt servicing capacity"""
    metrics = []
    anomalies = []
    
    # Identify loan/debt payments
    debt_keywords = ['loan', 'installment', 'repayment', 'emi', 'mortgage']
    debt_df = df[df['description'].str.lower().str.contains('|'.join(debt_keywords), na=False)]
    
    total_income = df[df['type'] == 'credit']['amount'].sum()
    total_debt_payments = debt_df['amount'].sum()
    
    debt_service_ratio = total_debt_payments / total_income if total_income > 0 else 0
    
    metrics.extend([
        KeyMetric(name="Total Debt Payments", value=round(total_debt_payments, 2), unit=currency,
                 description="Total amount paid towards debts"),
        KeyMetric(name="Debt Service Ratio", value=round(debt_service_ratio, 3),
                 description="Ratio of debt payments to total income"),
        KeyMetric(name="Number of Debt Payments", value=len(debt_df),
                 description="Count of debt payment transactions")
    ])
    
    # Alert for high debt service ratio
    if debt_service_ratio > 0.4:  # More than 40% of income goes to debt
        anomalies.append(Anomaly(
            type="High Debt Service Ratio",
            description=f"Debt payments consume {debt_service_ratio:.1%} of total income",
            reason="High debt burden may indicate financial stress"
        ))
    
    return {"metrics": metrics, "anomalies": anomalies, "debt_service_ratio": debt_service_ratio}

async def _analyze_liquidity_savings(df: pd.DataFrame, currency: str) -> Dict[str, Any]:
    """Analyzes liquidity and savings patterns"""
    metrics = []
    anomalies = []
    
    # Estimate emergency fund (assuming it's reflected in account balance)
    if 'balance_after' in df.columns and not df['balance_after'].isnull().all():
        avg_balance = df['balance_after'].mean()
        min_balance = df['balance_after'].min()
        
        # Estimate monthly expenses
        monthly_expenses = df[df['type'] == 'debit']['amount'].sum() / (len(df['date'].dt.to_period('M').unique()) or 1)
        emergency_fund_months = avg_balance / monthly_expenses if monthly_expenses > 0 else 0
        
        metrics.extend([
            KeyMetric(name="Average Account Balance", value=round(avg_balance, 2), unit=currency,
                     description="Average account balance maintained"),
            KeyMetric(name="Minimum Balance", value=round(min_balance, 2), unit=currency,
                     description="Lowest account balance recorded"),
            KeyMetric(name="Emergency Fund Coverage", value=round(emergency_fund_months, 1), unit="months",
                     description="Months of expenses covered by average balance")
        ])
        
        # Alert for low emergency fund
        if emergency_fund_months < 1:
            anomalies.append(Anomaly(
                type="Low Emergency Fund",
                description=f"Average balance covers only {emergency_fund_months:.1f} months of expenses",
                reason="Insufficient emergency fund for financial security"
            ))
        
        # Alert for negative balance
        if min_balance < 0:
            anomalies.append(Anomaly(
                type="Overdraft Usage",
                description=f"Account went negative to {currency} {min_balance:.2f}",
                reason="Overdraft usage indicates potential cash flow issues"
            ))
    else:
        emergency_fund_months = 0
    
    return {"metrics": metrics, "anomalies": anomalies, "emergency_fund_months": emergency_fund_months}

async def _analyze_account_behavior(df: pd.DataFrame, currency: str) -> Dict[str, Any]:
    """Analyzes account usage behavior"""
    metrics = []
    anomalies = []
    
    # Overdraft analysis
    overdraft_days = 0
    overdraft_frequency = 0
    
    if 'balance_after' in df.columns and not df['balance_after'].isnull().all():
        overdraft_days = (df['balance_after'] < 0).sum()
        overdraft_frequency = overdraft_days / len(df) if len(df) > 0 else 0
    
    # Transaction frequency analysis
    daily_tx_count = df.groupby('date').size()
    avg_daily_transactions = daily_tx_count.mean()
    max_daily_transactions = daily_tx_count.max()
    
    metrics.extend([
        KeyMetric(name="Overdraft Days", value=overdraft_days,
                 description="Number of days account balance was negative"),
        KeyMetric(name="Overdraft Frequency", value=round(overdraft_frequency, 3),
                 description="Proportion of time account was overdrawn"),
        KeyMetric(name="Average Daily Transactions", value=round(avg_daily_transactions, 1),
                 description="Average number of transactions per day"),
        KeyMetric(name="Maximum Daily Transactions", value=max_daily_transactions,
                 description="Highest number of transactions in a single day")
    ])
    
    # High transaction frequency anomaly
    if max_daily_transactions > 20:
        anomalies.append(Anomaly(
            type="High Transaction Activity",
            description=f"Unusually high number of transactions ({max_daily_transactions}) in a single day",
            reason="May indicate automated trading or unusual account activity"
        ))
    
    return {"metrics": metrics, "anomalies": anomalies, "overdraft_frequency": overdraft_frequency}
