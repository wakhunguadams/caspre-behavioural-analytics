import os
from io import BytesIO
from typing import BinaryIO
from app.core.config import settings
import asyncio # For running blocking cloud client calls in a thread
from datetime import datetime

# Conditional imports for cloud storage clients
# Ensure these libraries are installed based on your CLOUD_STORAGE_PROVIDER setting.
# For example, if CLOUD_STORAGE_PROVIDER is GCS, you need google-cloud-storage.
# If AWS_S3, you need boto3.
# The try-except blocks handle cases where they might not be installed.

if settings.CLOUD_STORAGE_PROVIDER == "AWS_S3":
    try:
        import boto3
    except ImportError:
        boto3 = None
        print("Boto3 (AWS SDK) not installed. AWS S3 storage will not function.")
elif settings.CLOUD_STORAGE_PROVIDER == "GCS":
    try:
        from google.cloud import storage
    except ImportError:
        storage = None
        print("Google Cloud Storage library not installed. GCS storage will not function.")

async def upload_file_to_cloud(
    file_content: BinaryIO, company_id: str, customer_id: str, filename: str
) -> str:
    """Uploads a file to cloud storage (S3 or GCS) and returns its URL/path."""
    try:
        # Generate a unique key for the object in storage
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        object_key = f"{company_id}/{customer_id}/bank_statements/{unique_filename}"

        if settings.CLOUD_STORAGE_PROVIDER == "AWS_S3" and boto3:
            s3_client = boto3.client(
                's3',
                region_name=settings.AWS_REGION_NAME,
                # AWS credentials typically handled by environment variables or IAM roles
            )
            # boto3 operations are synchronous, so run in a thread pool
            await asyncio.to_thread(
                s3_client.put_object,
                Bucket=settings.AWS_S3_BUCKET_NAME,
                Key=object_key,
                Body=file_content.getvalue(), # Pass bytes content
                ContentType="application/pdf" # Or appropriate content type based on filename
            )
            file_url = f"s3://{settings.AWS_S3_BUCKET_NAME}/{object_key}"
        elif settings.CLOUD_STORAGE_PROVIDER == "GCS" and storage:
            gcs_client = storage.Client(project=settings.GCP_PROJECT_ID)
            bucket = gcs_client.bucket(settings.GCS_BUCKET_NAME)
            blob = bucket.blob(object_key)
            # Google Cloud Storage client operations are synchronous, run in thread
            await asyncio.to_thread(
                blob.upload_from_file,
                file_content, # Pass the BytesIO object directly
                content_type="application/pdf"
            )
            file_url = f"gs://{settings.GCS_BUCKET_NAME}/{object_key}"
        else:
            raise ValueError(f"Unsupported CLOUD_STORAGE_PROVIDER '{settings.CLOUD_STORAGE_PROVIDER}' or missing library.")

        print(f"File uploaded to {file_url}")
        return file_url
    except Exception as e:
        print(f"Error uploading file to cloud storage: {e}")
        raise # Re-raise for error handling upstream

async def download_file_from_cloud(file_url: str) -> BytesIO:
    """Downloads a file from cloud storage and returns its content as BytesIO."""
    try:
        file_content = BytesIO()

        if settings.CLOUD_STORAGE_PROVIDER == "AWS_S3" and boto3:
            s3_client = boto3.client('s3', region_name=settings.AWS_REGION_NAME)
            # Parse bucket and key from the s3:// URL
            parts = file_url.replace("s3://", "").split('/', 1)
            bucket_name = parts[0]
            object_key = parts[1]
            
            response = await asyncio.to_thread(s3_client.get_object, Bucket=bucket_name, Key=object_key)
            # 'Body' is a StreamingBody, read its content
            file_content.write(await asyncio.to_thread(response['Body'].read))
            file_content.seek(0) # Reset pointer to the beginning of the BytesIO object

        elif settings.CLOUD_STORAGE_PROVIDER == "GCS" and storage:
            gcs_client = storage.Client(project=settings.GCP_PROJECT_ID)
            # Parse bucket and blob name from the gs:// URL
            parts = file_url.replace("gs://", "").split('/', 1)
            bucket_name = parts[0]
            object_key = parts[1]

            bucket = gcs_client.bucket(bucket_name)
            blob = bucket.blob(object_key)
            
            # download_to_file is synchronous, so use to_thread
            await asyncio.to_thread(blob.download_to_file, file_content)
            file_content.seek(0) # Reset pointer to the beginning

        else:
            raise ValueError(f"Unsupported CLOUD_STORAGE_PROVIDER '{settings.CLOUD_STORAGE_PROVIDER}' or missing library.")
        
        return file_content
    except Exception as e:
        print(f"Error downloading file from cloud storage: {e}")
        raise