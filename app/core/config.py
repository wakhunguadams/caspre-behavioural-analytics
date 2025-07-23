from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os

class Settings(BaseSettings):
    # loads .env file variables, 'extra="ignore"' to ignore unknown fields
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Behavioral Analytics Service"
    API_V1_STR: str = "/api/v1"

    # Database Settings (MySQL for structured data, Mongo for documents/logs)
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "password"
    MYSQL_SERVER: str = "localhost"
    MYSQL_PORT: int = 3306 # Default MySQL port
    MYSQL_DB: str = "behavioral_analytics_db"
    DATABASE_URL: str = "" # Constructed below

    MONGO_DB_URI: str = "mongodb://localhost:27017/"
    MONGO_DB_NAME: str = "bank_statements_db"

    # Cloud Storage (AWS S3 or Google Cloud Storage)
    CLOUD_STORAGE_PROVIDER: str = "GCS" # or "AWS_S3"
    AWS_S3_BUCKET_NAME: str = "your-aws-s3-bucket"
    GCS_BUCKET_NAME: str = "your-gcs-bucket"
    GCP_PROJECT_ID: str = "your-gcp-project-id"
    AWS_REGION_NAME: str = "af-south-1" # African region example

    # Message Queue (Kafka)
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_BANK_STATEMENT_UPLOAD: str = "bank_statement_uploads"
    KAFKA_TOPIC_ANALYTICS_RESULTS: str = "analytics_results"

    # Google Gemini API Key
    GEMINI_API_KEY: str = "YOUR_GEMINI_API_KEY"

    # Document AI Processor ID (if using GCP Document AI)
    GCP_DOC_AI_PROCESSOR_ID: str = "" # e.g., "your-processor-id"
    GCP_DOC_AI_LOCATION: str = "us" # or "eu", "africa-south1" if available

    # Security
    TENANT_AUTH_HEADER: str = "X-Company-ID" # Header to extract tenant ID
    CUSTOMER_AUTH_HEADER: str = "X-Customer-ID" # Header to extract customer ID

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.DATABASE_URL:
            # Using aiomysql driver for async support with Databases library
            self.DATABASE_URL = (
                f"mysql+aiomysql://{self.MYSQL_USER}:"
                f"{self.MYSQL_PASSWORD}@{self.MYSQL_SERVER}:"
                f"{self.MYSQL_PORT}/{self.MYSQL_DB}"
            )

# Load settings from .env file
settings = Settings()