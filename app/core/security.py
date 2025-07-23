from fastapi import Header, HTTPException
from typing import Annotated
from app.core.config import settings

# This dependency ensures tenant and customer IDs are present in headers
async def get_tenant_and_customer_ids(
    company_id: Annotated[str, Header(alias=settings.TENANT_AUTH_HEADER)],
    customer_id: Annotated[str, Header(alias=settings.CUSTOMER_AUTH_HEADER)],
):
    """
    FastAPI dependency to extract and validate X-Company-ID and X-Customer-ID headers.
    In a production system, this would also involve authentication/authorization logic
    (e.g., JWT validation, API key lookup).
    """
    if not company_id:
        raise HTTPException(status_code=400, detail=f"{settings.TENANT_AUTH_HEADER} header is required.")
    if not customer_id:
        raise HTTPException(status_code=400, detail=f"{settings.CUSTOMER_AUTH_HEADER} header is required.")
    return {"company_id": company_id, "customer_id": customer_id}