from app.core.db import database, Base # Import Base and database
from sqlalchemy import Column, String, JSON, Boolean, Integer, Float
from sqlalchemy.future import select # For async select
from sqlalchemy.dialects.mysql import JSON as MySQLJSON # Specific JSON type for MySQL
from sqlalchemy.ext.declarative import declarative_base # Import explicitly
from typing import Dict, Any, Optional
import json

# Define the SQLAlchemy ORM model for tenant configurations
class TenantConfigDB(Base):
    __tablename__ = "tenant_configurations"

    company_id = Column(String(255), primary_key=True, index=True)
    language_preference = Column(String(10), default="en")
    currency_preference = Column(String(10), default="KES")
    timezone = Column(String(50), default="Africa/Nairobi")
    
    # Use MySQLJSON for explicit JSON type for MySQL.
    # It stores as VARCHAR/TEXT internally and requires json.dumps/loads for objects.
    bank_statement_formats = Column(MySQLJSON, default=json.dumps([]))
    transaction_categorization_rules = Column(MySQLJSON, default=json.dumps({}))
    behavioral_scoring_weights = Column(MySQLJSON, default=json.dumps({}))
    llm_tone_guidelines = Column(MySQLJSON, default=json.dumps({}))
    
    data_residency_region = Column(String(50), default="global")
    is_active = Column(Boolean, default=True)
    max_file_size_mb = Column(Integer, default=20)
    supported_file_types = Column(MySQLJSON, default=json.dumps(["pdf", "jpg", "png"]))

    def to_dict(self) -> Dict[str, Any]:
        """Converts SQLAlchemy model instance to a dictionary, handling JSON fields."""
        data = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, str) and column.type.__class__ is MySQLJSON:
                try:
                    data[column.name] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    data[column.name] = value # Fallback if not valid JSON string
            else:
                data[column.name] = value
        return data

async def get_tenant_config(company_id: str) -> Optional[Dict[str, Any]]:
    """Fetches configuration for a specific tenant."""
    query = select(TenantConfigDB).where(TenantConfigDB.company_id == company_id)
    result = await database.fetch_one(query)
    if result:
        # Convert Row object to TenantConfigDB instance, then to dictionary
        return TenantConfigDB(**result._mapping).to_dict()
    return None

async def create_default_tenant_config(company_id: str) -> Dict[str, Any]:
    """Creates a default configuration for a new tenant."""
    config_data = {
        "company_id": company_id,
        "language_preference": "en",
        "currency_preference": "KES",
        "timezone": "Africa/Nairobi",
        "bank_statement_formats": json.dumps([]), # Store as JSON string
        "transaction_categorization_rules": json.dumps({
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
        }),
        "behavioral_scoring_weights": json.dumps({
            "income_stability_impact": 0.3,
            "debt_ratio_impact": 0.25,
            "savings_rate_impact": 0.2,
            "discretionary_spending_impact": 0.15,
            "anomaly_penalty": 0.1
        }),
        "llm_tone_guidelines": json.dumps({
            "professional": True,
            "concise": True,
            "avoid_jargon": False,
            "include_disclaimers": True
        }),
        "data_residency_region": "global",
        "is_active": True,
        "max_file_size_mb": 20,
        "supported_file_types": json.dumps(["pdf", "jpg", "png"])
    }
    
    # Using the ORM model to insert
    query = TenantConfigDB.__table__.insert().values(**config_data)
    await database.execute(query)
    print(f"Created default config for tenant: {company_id}")
    return await get_tenant_config(company_id) # Fetch to ensure JSON parsing

async def update_tenant_config(company_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates configuration for a specific tenant."""
    # Ensure JSON fields are stringified before update
    for key in ['bank_statement_formats', 'transaction_categorization_rules',
                'behavioral_scoring_weights', 'llm_tone_guidelines', 'supported_file_types']:
        if key in updates and not isinstance(updates[key], str):
            updates[key] = json.dumps(updates[key])
            
    query = TenantConfigDB.__table__.update().where(TenantConfigDB.__table__.c.company_id == company_id).values(**updates)
    await database.execute(query)
    updated_config = await get_tenant_config(company_id)
    return updated_config