import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.schemas.responses import Transaction, KeyMetric, Anomaly
from app.utils.tenant_config import get_tenant_config
from tsfresh import extract_features
from tsfresh.utilities.dataframe_functions import impute
from tsfresh.feature_extraction import EfficientFCParameters
import numpy as np

async def perform_feature_engineering(
    extracted_transactions: List[Transaction], company_id: str, customer_id: str
) -> Dict[str, Any]:
    """
    Transforms raw transactions into rich behavioral features.
    """
    if not extracted_transactions:
        return {"all_features": {}, "key_metrics": [], "categorized_transactions": [], "anomalies_detected": []}

    # Convert list of Pydantic models to Pandas DataFrame
    df = pd.DataFrame([t.model_dump() for t in extracted_transactions])
    
    # Ensure date column is datetime objects
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date') # Drop rows with invalid dates

    if df.empty:
        return {"all_features": {}, "key_metrics": [], "categorized_transactions": [], "anomalies_detected": []}

    # Prepare amount columns
    df['credit_amount'] = df.apply(lambda row: row['amount'] if row['type'] == 'credit' else 0, axis=1)
    df['debit_amount'] = df.apply(lambda row: row['amount'] if row['type'] == 'debit' else 0, axis=1)
    
    # Fill missing balance_after if possible, assuming initial balance might be missing
    # This is a heuristic and needs careful consideration for real data
    if df['balance_after'].isnull().any():
        print("Warning: 'balance_after' column has missing values. Attempting to infer.")
        # Calculate net change for each transaction
        df['net_change'] = df['credit_amount'] - df['debit_amount']
        
        # If the first balance is missing, assume it's 0 or infer from first transaction
        if df['balance_after'].iloc[0] is None or pd.isna(df['balance_after'].iloc[0]):
            # Start running balance from the first net change if no initial balance
            df['balance_after'] = df['net_change'].cumsum()
        else:
            # If first balance exists, apply cumulative sum from there
            initial_balance = df['balance_after'].iloc[0]
            df['balance_after'] = initial_balance + df['net_change'].cumsum() - df['net_change'].iloc[0]
            # Adjust the first row's balance to be correct if it was an actual starting balance
            df.loc[df.index[0], 'balance_after'] = initial_balance
            
    df = df.drop(columns=['net_change'], errors='ignore') # Clean up temp column

    # --- 1. Transaction Categorization ---
    tenant_config = await get_tenant_config(company_id)
    # Default categorization rules if not found for tenant
    categorization_rules = tenant_config.get("transaction_categorization_rules", {})
    if not categorization_rules:
        # Fallback to a sensible default if tenant has no rules
        categorization_rules = {
            "income": ["salary", "payroll", "deposit"],
            "rent": ["rent", "landlord"],
            "utilities": ["kplc", "water", "electricity", "utility", "internet"],
            "transport": ["fuel", "petrol", "uber", "matatu", "bus"],
            "groceries": ["supermarket", "grocery", "naivas", "carrefour"],
            "loan_repayment": ["loan payment", "instalment", "repayment"],
            "entertainment": ["restaurant", "bar", "club", "movie", "leisure"],
            "savings": ["savings deposit", "fixed deposit", "investment"],
            "withdrawal": ["atm withdrawal", "cash out"],
            "transfer_out": ["transfer to"],
            "transfer_in": ["transfer from"]
        }


    def categorize_transaction(description: str) -> str:
        description_lower = description.lower()
        for category, keywords in categorization_rules.items():
            if any(kw.lower() in description_lower for kw in keywords):
                return category
        return "Uncategorized"

    df['category'] = df['description'].apply(categorize_transaction)

    # --- 2. Rich Behavioral Features ---
    key_metrics: List[KeyMetric] = []
    currency = tenant_config.get("currency_preference", "KES")

    # Income Stability
    income_df = df[df['category'] == 'income']
    if not income_df.empty:
        # Aggregate income by month
        income_by_month = income_df.set_index('date').resample('MS')['credit_amount'].sum().reset_index()
        avg_monthly_income = income_by_month['credit_amount'].mean()
        std_monthly_income = income_by_month['credit_amount'].std()
        
        income_consistency = 1 - (std_monthly_income / avg_monthly_income if avg_monthly_income > 0 else 1) # Higher is more consistent
        
        key_metrics.append(KeyMetric(name="Average Monthly Income", value=round(avg_monthly_income, 2), unit=currency, description="Average income received per month."))
        key_metrics.append(KeyMetric(name="Income Consistency (0-1)", value=round(income_consistency, 2), description="Higher indicates more stable income."))
    else:
        key_metrics.append(KeyMetric(name="Average Monthly Income", value=0, unit=currency, description="No income transactions detected."))
        key_metrics.append(KeyMetric(name="Income Consistency (0-1)", value=0, description="No income transactions detected."))

    # Spending Patterns
    total_spending = df['debit_amount'].sum()
    total_credit = df['credit_amount'].sum()
    spending_to_income_ratio = (total_spending / total_credit) if total_credit else 0
    key_metrics.append(KeyMetric(name="Total Spending", value=round(total_spending, 2), unit=currency, description="Total amount spent."))
    key_metrics.append(KeyMetric(name="Spending to Income Ratio", value=round(spending_to_income_ratio, 2), description="Percentage of total credit spent."))

    # Spending by Category
    spending_by_category = df.groupby('category')['debit_amount'].sum().to_dict()
    key_metrics.append(KeyMetric(name="Spending By Category", value=spending_by_category, description="Breakdown of spending by categorized types."))

    # Debt Servicing Capacity
    loan_repayments = df[df['category'] == 'loan_repayment']['debit_amount'].sum()
    key_metrics.append(KeyMetric(name="Total Loan Repayments", value=round(loan_repayments, 2), unit=currency, description="Sum of categorized loan repayments."))
    
    # Financial Health Indicators
    # Average Daily Balance
    if 'balance_after' in df.columns and not df['balance_after'].empty:
        avg_daily_balance = df['balance_after'].mean()
        min_balance = df['balance_after'].min()
        max_balance = df['balance_after'].max()
        key_metrics.append(KeyMetric(name="Average Daily Balance", value=round(avg_daily_balance, 2), unit=currency, description="Average balance maintained over the period."))
        key_metrics.append(KeyMetric(name="Minimum Balance", value=round(min_balance, 2), unit=currency, description="Lowest balance recorded."))
        key_metrics.append(KeyMetric(name="Maximum Balance", value=round(max_balance, 2), unit=currency, description="Highest balance recorded."))
        
        # Savings Rate (simplified: based on deposits to 'savings' category)
        total_savings_deposits = df[df['category'] == 'savings']['credit_amount'].sum()
        savings_rate = (total_savings_deposits / total_credit) if total_credit else 0
        key_metrics.append(KeyMetric(name="Savings Rate", value=round(savings_rate * 100, 2), unit="%", description="Percentage of total credit allocated to savings."))
    else:
        key_metrics.append(KeyMetric(name="Average Daily Balance", value=0, unit=currency))
        key_metrics.append(KeyMetric(name="Minimum Balance", value=0, unit=currency))
        key_metrics.append(KeyMetric(name="Maximum Balance", value=0, unit=currency))
        key_metrics.append(KeyMetric(name="Savings Rate", value=0, unit="%"))


    # --- 3. Time-Series Analysis & Anomaly Detection (using tsfresh and simple rules) ---
    anomalies_detected: List[Anomaly] = []

    # Prepare DataFrame for tsfresh (if you need complex time-series features beyond simple aggregations)
    # Tsfresh expects a DataFrame with 'id', 'time', and value columns.
    # For a single customer, 'id' can be constant. 'time' should be numerical.
    # ts_df = df[['date', 'debit_amount', 'credit_amount', 'balance_after']].copy()
    # ts_df['id'] = customer_id
    # ts_df['time'] = (ts_df['date'] - ts_df['date'].min()).dt.total_seconds() # Time in seconds from first transaction

    # # Ensure time series is sufficiently long and varied for tsfresh
    # if len(ts_df['id'].unique()) == 1 and len(ts_df) > 10: # Needs at least some transactions
    #     settings_tsfresh = EfficientFCParameters()
    #     try:
    #         X_extracted = extract_features(ts_df,
    #                                        column_id='id',
    #                                        column_sort='time',
    #                                        default_fc_parameters=settings_tsfresh,
    #                                        impute_function=impute,
    #                                        show_warnings=False)
    #         tsfresh_features_dict = X_extracted.loc[customer_id].to_dict() if customer_id in X_extracted.index else {}
    #         key_metrics.append(KeyMetric(name="TSFresh Features", value=tsfresh_features_dict, description="Advanced time-series features extracted by tsfresh."))
    #     except Exception as e:
    #         print(f"TSFresh feature extraction failed: {e}")
    # else:
    #     print("Skipping tsfresh: Insufficient data or format for time-series analysis.")


    # Simplified Anomaly Detection (rule-based for demonstration)
    # This should be replaced by proper ML-based anomaly detection models.
    
    # Rule 1: Large single debit transaction (e.g., > 3 * average daily spending)
    if total_spending > 0 and not df[df['type'] == 'debit'].empty:
        avg_daily_debit = df[df['type'] == 'debit'].groupby('date')['amount'].sum().mean()
        for _, row in df[df['type'] == 'debit'].iterrows():
            if row['amount'] > (avg_daily_debit * 3) and row['amount'] > 1000: # Example threshold
                anomalies_detected.append(Anomaly(
                    type="Unusually Large Debit",
                    description=f"Transaction of {currency} {row['amount']:.2f} is significantly larger than typical spending.",
                    transaction=row.to_dict()
                ))
    
    # Rule 2: Frequent small transactions (potential micro-lending repayments, gambling, or unusual activity)
    # Count transactions per day
    tx_count_per_day = df.groupby(df['date'].dt.date)['amount'].count()
    if not tx_count_per_day.empty and tx_count_per_day.max() > 10: # Example: more than 10 transactions on a single day
        anomalous_days = tx_count_per_day[tx_count_per_day > 10].index.tolist()
        for day in anomalous_days:
            anomalies_detected.append(Anomaly(
                type="High Transaction Frequency",
                description=f"Multiple small transactions detected on {day}, potentially indicating unusual activity.",
                reason=f"{tx_count_per_day.loc[day]} transactions on this day."
            ))

    # Convert DataFrame transactions back to Pydantic models if needed for the response
    categorized_transactions_list = [Transaction(**row.to_dict()) for _, row in df.iterrows()]

    return {
        "all_features": {
            # You would put the actual feature vector used by the scoring model here
            "avg_monthly_income": avg_monthly_income if 'avg_monthly_income' in locals() else 0,
            "income_consistency": income_consistency if 'income_consistency' in locals() else 0,
            "total_spending": total_spending,
            "spending_to_income_ratio": spending_to_income_ratio,
            "loan_repayments": loan_repayments,
            "avg_daily_balance": avg_daily_balance if 'avg_daily_balance' in locals() else 0,
            "min_balance": min_balance if 'min_balance' in locals() else 0,
            "max_balance": max_balance if 'max_balance' in locals() else 0,
            "savings_rate": savings_rate if 'savings_rate' in locals() else 0
            # ... add more features as you develop them
        },
        "key_metrics": key_metrics,
        "categorized_transactions": categorized_transactions_list,
        "anomalies_detected": anomalies_detected
    }