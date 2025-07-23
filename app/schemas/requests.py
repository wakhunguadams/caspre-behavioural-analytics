from pydantic import BaseModel, Field
from typing import Optional

# Request body for the initial file upload (file is handled separately by FastAPI's UploadFile)
class BankStatementUploadRequest(BaseModel):
    # company_id and customer_id are expected from headers
    callback_url: Optional[str] = Field(None, description="Optional URL for async result notification.")

class BehavioralAnalyticsJob(BaseModel):
    """Schema for the message pushed to Kafka."""
    job_id: str = Field(..., description="Unique ID for the analytics job.")
    company_id: str
    customer_id: str
    file_url: str = Field(..., description="URL to the uploaded bank statement in cloud storage.")
    filename: str = Field(..., description="Original filename of the statement.")
    callback_url: Optional[str] = Field(None, description="Optional URL for async result notification.")

class JobStatusResponse(BaseModel):
    """Schema for responding to job status queries."""
    job_id: str
    status: str = Field(..., description="Current status of the analytics job.")
    message: Optional[str] = Field(None, description="Detailed message about the job status.")
    result_url: Optional[str] = Field(None, description="URL where the final analysis results can be fetched if completed.")