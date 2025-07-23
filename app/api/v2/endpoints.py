from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException, BackgroundTasks, status
from typing import Annotated
from uuid import uuid4
from datetime import datetime
from app.schemas.requests import BankStatementUploadRequest, BehavioralAnalyticsJob, JobStatusResponse
from app.schemas.responses import BehavioralAnalyticsResult
from app.core.config import settings
from app.core.security import get_tenant_and_customer_ids
from app.core.messaging import send_message_to_kafka
from app.services.idp_processor import process_document_with_idp
from app.services.feature_engineer import perform_feature_engineering
from app.services.scoring_model import calculate_behavioral_score
from app.services.llm_insights import generate_behavioral_summary
from app.utils.file_storage import upload_file_to_cloud
from app.core.db import get_mongo_db, database # Import database for MySQL operations
from app.utils.tenant_config import get_tenant_config, create_default_tenant_config
from motor.motor_asyncio import AsyncIOMotorDatabase
from databases import Database as MySQLDatabase # Alias to avoid conflict with Mongo

router = APIRouter()

# In-memory storage for job statuses (for demonstration purposes only)
# In a real system, this would be persisted in a database (e.g., MySQL)
job_statuses = {}

# --- Helper function for background processing (Kafka consumer will do this) ---
async def _process_bank_statement_job(job_payload: BehavioralAnalyticsJob):
    job_id = job_payload.job_id
    company_id = job_payload.company_id
    customer_id = job_payload.customer_id
    file_url = job_payload.file_url
    filename = job_payload.filename
    callback_url = job_payload.callback_url

    mongo_db = get_mongo_db() # Get MongoDB client

    try:
        job_statuses[job_id] = {"status": "PROCESSING", "message": "Starting IDP processing..."}

        # 1. Fetch Tenant Configuration
        tenant_config = await get_tenant_config(company_id)
        if not tenant_config:
            # If no config, create a default one (or raise error based on policy)
            print(f"No tenant config found for {company_id}. Creating default.")
            tenant_config = await create_default_tenant_config(company_id)

        # 2. IDP Processing (Extract Transactions)
        idp_data = await process_document_with_idp(file_url, tenant_config)
        extracted_transactions = idp_data.get("transactions", [])
        full_text = idp_data.get("full_text", "")
        if not extracted_transactions:
            job_statuses[job_id] = {"status": "FAILED", "message": "Failed to extract any transactions from the document."}
            # Log full text for debugging
            await mongo_db["processing_logs"].insert_one({
                "job_id": job_id,
                "company_id": company_id,
                "customer_id": customer_id,
                "filename": filename,
                "file_url": file_url,
                "status": "failed",
                "error": "No transactions extracted by IDP.",
                "raw_text_extracted": full_text, # Store raw text for debugging
                "timestamp": datetime.now().isoformat()
            })
            if callback_url:
                # In a real system, send POST request to callback_url with failure
                print(f"Sending failure callback to {callback_url}")
            return

        job_statuses[job_id] = {"status": "PROCESSING", "message": "Performing feature engineering..."}

        # 3. Feature Engineering & Anomaly Detection
        feature_engineering_results = await perform_feature_engineering(
            extracted_transactions, company_id, customer_id
        )
        all_features = feature_engineering_results["all_features"]
        key_metrics = feature_engineering_results["key_metrics"]
        categorized_transactions = feature_engineering_results["categorized_transactions"]
        anomalies_detected = feature_engineering_results["anomalies_detected"]

        job_statuses[job_id] = {"status": "PROCESSING", "message": "Calculating behavioral score..."}

        # 4. Behavioral Scoring
        scoring_results = await calculate_behavioral_score(
            customer_id, all_features, anomalies_detected, company_id
        )
        behavioral_score = scoring_results["behavioral_score"]
        score_explanation = scoring_results["score_explanation"]
        rule_engine_breakdown = scoring_results["rule_engine_breakdown"]

        job_statuses[job_id] = {"status": "PROCESSING", "message": "Generating LLM insights..."}

        # 5. LLM Insights Generation
        analysis_summary = await generate_behavioral_summary(
            customer_id, key_metrics, anomalies_detected, rule_engine_breakdown, behavioral_score, score_explanation, tenant_config
        )

        # 6. Store Results in MongoDB
        final_result = BehavioralAnalyticsResult(
            company_id=company_id,
            customer_id=customer_id,
            job_id=job_id,
            status="completed",
            behavioral_score=behavioral_score,
            score_explanation=score_explanation,
            analysis_summary=analysis_summary,
            key_metrics=[m.model_dump() for m in key_metrics],
            categorized_transactions=[t.model_dump() for t in categorized_transactions],
            anomalies_detected=[a.model_dump() for a in anomalies_detected],
            rule_engine_breakdown=[r.model_dump() for r in rule_engine_breakdown],
            localization_details={
                "language": tenant_config.get("language_preference"),
                "currency": tenant_config.get("currency_preference"),
                "timezone": tenant_config.get("timezone")
            },
            processed_at=datetime.now().isoformat()
        )
        
        await mongo_db["analytics_results"].insert_one(final_result.model_dump())
        
        result_url = f"/api/v1/analytics/results/{job_id}" # URL to fetch results

        job_statuses[job_id] = {
            "status": "COMPLETED",
            "message": "Analysis completed successfully.",
            "result_url": result_url
        }

        # 7. Publish Result to Kafka (for other services to consume)
        await send_message_to_kafka(
            settings.KAFKA_TOPIC_ANALYTICS_RESULTS,
            {
                "job_id": job_id,
                "company_id": company_id,
                "customer_id": customer_id,
                "status": "COMPLETED",
                "result_url": result_url,
                "brief_summary": analysis_summary[:200] + "..." # Send a short summary
            }
        )

        # 8. Send Callback (if provided)
        if callback_url:
            # In a real system, use an aiohttp client to send POST request
            print(f"Sending success callback to {callback_url} with result_url: {result_url}")

    except Exception as e:
        error_message = f"Analysis failed: {e}"
        print(f"Error processing job {job_id}: {error_message}")
        job_statuses[job_id] = {"status": "FAILED", "message": error_message}
        
        # Log error in MongoDB
        await mongo_db["processing_logs"].insert_one({
            "job_id": job_id,
            "company_id": company_id,
            "customer_id": customer_id,
            "filename": filename,
            "file_url": file_url,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        # Publish failure to Kafka
        await send_message_to_kafka(
            settings.KAFKA_TOPIC_ANALYTICS_RESULTS,
            {
                "job_id": job_id,
                "company_id": company_id,
                "customer_id": customer_id,
                "status": "FAILED",
                "error_message": error_message
            }
        )
        if callback_url:
            # Send POST request to callback_url with failure details
            print(f"Sending failure callback to {callback_url}")


# --- API Endpoints ---

@router.post(
    "/upload-bank-statement", 
    response_model=JobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a bank statement for behavioral analysis"
)
async def upload_bank_statement(
    file: Annotated[UploadFile, File(description="Bank statement file (PDF, JPG, PNG)")],
    auth_ids: Annotated[dict, Depends(get_tenant_and_customer_ids)],
    request_body: BankStatementUploadRequest = Depends(), # Use Depends for JSON body
):
    """
    Initiates the behavioral analytics process by uploading a bank statement.
    The file is stored, and an asynchronous job is created and queued.
    """
    company_id = auth_ids["company_id"]
    customer_id = auth_ids["customer_id"]
    callback_url = request_body.callback_url

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # Validate file type (simple check)
    allowed_types = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Only PDF, JPG, PNG are allowed."
        )
    
    # Read file content into BytesIO for cloud upload
    file_content = await file.read()
    file_content_bytesio = BytesIO(file_content)

    # Generate a unique job ID
    job_id = str(uuid4())

    try:
        # Upload file to cloud storage
        file_url = await upload_file_to_cloud(
            file_content_bytesio, company_id, customer_id, file.filename
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to cloud storage: {e}")

    # Create job payload
    job_payload = BehavioralAnalyticsJob(
        job_id=job_id,
        company_id=company_id,
        customer_id=customer_id,
        file_url=file_url,
        filename=file.filename,
        callback_url=callback_url
    )

    # Store initial job status
    job_statuses[job_id] = {"status": "QUEUED", "message": "Job queued for processing."}

    # Publish job to Kafka (asynchronous processing)
    # In a real system, a dedicated Kafka consumer service would pick this up.
    await send_message_to_kafka(settings.KAFKA_TOPIC_BANK_STATEMENT_UPLOAD, job_payload.model_dump())
    
    return JobStatusResponse(
        job_id=job_id,
        status="QUEUED",
        message="Bank statement uploaded and analysis job queued. Use the job_id to check status."
    )

@router.get(
    "/analytics/status/{job_id}",
    response_model=JobStatusResponse,
    summary="Get the status of a behavioral analytics job"
)
async def get_analytics_job_status(job_id: str):
    """
    Retrieves the current status of a previously submitted behavioral analytics job.
    """
    status_info = job_statuses.get(job_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    return JobStatusResponse(**status_info)

@router.get(
    "/analytics/results/{job_id}",
    response_model=BehavioralAnalyticsResult,
    summary="Get the full behavioral analytics results for a completed job"
)
async def get_analytics_results(job_id: str, mongo_db: Annotated[AsyncIOMotorDatabase, Depends(get_mongo_db)]):
    """
    Retrieves the detailed behavioral analytics results for a completed job.
    """
    result = await mongo_db["analytics_results"].find_one({"job_id": job_id})
    if not result:
        # Check in-memory status first for more informative message
        status_info = job_statuses.get(job_id)
        if status_info and status_info.get("status") == "FAILED":
            raise HTTPException(status_code=400, detail=f"Job {job_id} failed: {status_info.get('message')}")
        elif status_info and status_info.get("status") != "COMPLETED":
            raise HTTPException(status_code=202, detail=f"Job {job_id} is still {status_info.get('status').lower()}. Results not yet available.")
        else:
            raise HTTPException(status_code=404, detail="Analytics results not found or job ID invalid.")
    
    # Convert MongoDB _id to string for Pydantic compatibility if present
    if "_id" in result:
        result["_id"] = str(result["_id"])
    
    return BehavioralAnalyticsResult(**result)

@router.put("/tenant-config/{company_id}", summary="Update tenant-specific configuration")
async def update_tenant_configuration(
    company_id: str,
    config_updates: Annotated[dict, Form(description="JSON string of updates")], # Allow JSON string in form-data for testing
    auth_ids: Annotated[dict, Depends(get_tenant_and_customer_ids)] # Ensure tenant ID matches path
):
    """
    Updates the configuration for a specific tenant, including customization for
    transaction categorization, LLM tone, and behavioral scoring weights.
    """
    # Verify company_id from path matches header (or implement proper admin auth)
    if company_id != auth_ids["company_id"]:
        raise HTTPException(status_code=403, detail="Forbidden: Company ID mismatch.")

    try:
        # Convert JSON string from Form to dict
        updates_dict = json.loads(config_updates)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for config_updates.")

    updated_config = await update_tenant_config(company_id, updates_dict)
    if not updated_config:
        raise HTTPException(status_code=404, detail="Tenant configuration not found to update.")
    return {"message": "Tenant configuration updated successfully", "config": updated_config}

@router.get("/tenant-config/{company_id}", summary="Get tenant-specific configuration")
async def get_tenant_configuration(
    company_id: str,
    auth_ids: Annotated[dict, Depends(get_tenant_and_customer_ids)] # Ensure tenant ID matches path
):
    """
    Retrieves the configuration for a specific tenant.
    """
    if company_id != auth_ids["company_id"]:
        raise HTTPException(status_code=403, detail="Forbidden: Company ID mismatch.")

    config = await get_tenant_config(company_id)
    if not config:
        # Optionally create default if not found
        config = await create_default_tenant_config(company_id)
        return {"message": "Default tenant configuration created and retrieved.", "config": config}
    return {"message": "Tenant configuration retrieved successfully", "config": config}