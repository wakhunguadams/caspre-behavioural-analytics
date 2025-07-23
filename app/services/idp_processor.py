import os
from io import BytesIO
from typing import Dict, Any, List
from datetime import datetime
from app.core.config import settings
from app.schemas.responses import Transaction
from app.utils.file_storage import download_file_from_cloud
import re
import asyncio # For running blocking cloud client calls in a thread

# Conditional imports for cloud IDP
if settings.CLOUD_STORAGE_PROVIDER == "GCS":
    try:
        from google.cloud import documentai_v1 as documentai
        from google.api_core.client_options import ClientOptions
    except ImportError:
        documentai = None
        ClientOptions = None
        print("Google Cloud Document AI libraries not installed. GCS IDP will not function.")
elif settings.CLOUD_STORAGE_PROVIDER == "AWS_S3":
    try:
        import boto3
    except ImportError:
        boto3 = None
        print("Boto3 (AWS SDK) not installed. AWS S3 IDP will not function.")

async def process_document_with_idp(file_url: str, tenant_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes a bank statement using an IDP service (Google Doc AI or AWS Textract).
    Returns extracted raw text and entities.
    """
    file_content_bytesio = await download_file_from_cloud(file_url)
    raw_bytes = file_content_bytesio.getvalue()

    extracted_data = {}

    if settings.CLOUD_STORAGE_PROVIDER == "GCS" and documentai and ClientOptions:
        try:
            # Document AI processor location must match region
            opts = ClientOptions(api_endpoint=f"{settings.GCP_DOC_AI_LOCATION}-documentai.googleapis.com")
            client = documentai.DocumentProcessorServiceClient(client_options=opts)
            name = client.processor_path(
                settings.GCP_PROJECT_ID, settings.GCP_DOC_AI_LOCATION, settings.GCP_DOC_AI_PROCESSOR_ID
            )

            raw_document = documentai.RawDocument(content=raw_bytes, mime_type="application/pdf")
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            
            # Document AI client calls are synchronous, so run in a thread
            result = await asyncio.to_thread(client.process_document, request)
            document = result.document
            
            extracted_data['full_text'] = document.text
            transactions = []
            
            # This part needs to be highly customized based on your Document AI processor's
            # entity extraction schema for bank statements.
            # Example: Iterate through detected entities that represent transactions.
            for entity in document.entities:
                if entity.type_ == "transaction_line": # Example: A custom entity for a full transaction line
                    try:
                        # Extract specific properties of the transaction entity
                        date = entity.properties.get("date").text_anchor.content if "date" in entity.properties else None
                        description = entity.properties.get("description").text_anchor.content if "description" in entity.properties else None
                        amount_str = entity.properties.get("amount").text_anchor.content if "amount" in entity.properties else None
                        type_str = entity.properties.get("type").text_anchor.content if "type" in entity.properties else 'unknown' # e.g., "DEBIT", "CREDIT"
                        balance_str = entity.properties.get("balance").text_anchor.content if "balance" in entity.properties else None

                        # Clean and convert amount
                        amount = float(re.sub(r'[^\d.-]', '', amount_str)) if amount_str else 0.0
                        balance_after = float(re.sub(r'[^\d.-]', '', balance_str)) if balance_str else None

                        transactions.append(Transaction(
                            date=date,
                            description=description,
                            amount=abs(amount), # Store absolute amount
                            type=type_str.lower(), # Ensure 'debit'/'credit'
                            balance_after=balance_after,
                            original_currency=tenant_config.get("currency_preference") # Infer from config
                        ))
                    except (AttributeError, ValueError, KeyError) as e:
                        print(f"Skipping malformed transaction entity: {entity.text_anchor.content} Error: {e}")

            extracted_data['transactions'] = transactions

        except Exception as e:
            print(f"Error with Google Document AI: {e}")
            extracted_data['error'] = f"Document AI processing failed: {e}"
            extracted_data['full_text'] = raw_bytes.decode('utf-8', errors='ignore')
            # Fallback to text extraction if DocAI fails
            extracted_data['transactions'] = await _extract_transactions_from_text_fallback(extracted_data['full_text'], tenant_config)


    elif settings.CLOUD_STORAGE_PROVIDER == "AWS_S3" and boto3:
        # AWS Textract Integration
        s3_bucket = file_url.replace("s3://", "").split('/', 1)[0]
        s3_key = file_url.replace("s3://", "").split('/', 1)[1]
        textract_client = boto3.client('textract', region_name=settings.AWS_REGION_NAME)
        try:
            # Start asynchronous job for multi-page PDFs
            response = await asyncio.to_thread(
                textract_client.start_document_analysis,
                DocumentLocation={'S3Object': {'Bucket': s3_bucket, 'Name': s3_key}},
                FeatureTypes=['FORMS', 'TABLES'] # Or 'ALL' for more comprehensive extraction
            )
            job_id = response['JobId']
            print(f"Textract analysis started with JobId: {job_id}. Polling for results...")

            # --- Polling for results (simplified, production should use SQS notifications) ---
            status = 'IN_PROGRESS'
            while status == 'IN_PROGRESS':
                await asyncio.sleep(5) # Wait 5 seconds before next poll
                get_results_response = await asyncio.to_thread(textract_client.get_document_analysis, JobId=job_id)
                status = get_results_response['JobStatus']
                print(f"Textract job {job_id} status: {status}")

            if status == 'SUCCEEDED':
                full_text = ""
                # This part requires iterating through Textract Blocks to reconstruct transactions
                # Textract's output is complex (pages, lines, words, tables, forms).
                # You'll need a dedicated parser for bank statements from Textract output.
                # Example: Iterate through `TABLE` blocks and then their `CELL` blocks.
                # This is a significant development effort for robust parsing.

                # For now, a very simplified extraction from lines
                for block in get_results_response.get('Blocks', []):
                    if block['BlockType'] == 'LINE':
                        full_text += block['Text'] + "\n"
                extracted_data['full_text'] = full_text
                extracted_data['transactions'] = await _extract_transactions_from_text_fallback(full_text, tenant_config)
            else:
                raise Exception(f"Textract job {job_id} failed with status: {status}")

        except Exception as e:
            print(f"Error with AWS Textract: {e}")
            extracted_data['error'] = f"Textract processing failed: {e}"
            extracted_data['full_text'] = raw_bytes.decode('utf-8', errors='ignore')
            extracted_data['transactions'] = await _extract_transactions_from_text_fallback(extracted_data['full_text'], tenant_config)
    else:
        # Fallback for unsupported provider or if cloud services fail
        extracted_data['full_text'] = raw_bytes.decode('utf-8', errors='ignore')
        extracted_data['transactions'] = await _extract_transactions_from_text_fallback(extracted_data['full_text'], tenant_config)

    return extracted_data

# --- Fallback/Generic Text-based Transaction Extractor ---
# This is a very basic regex-based extractor. Real-world statements are highly variable and complex.
# This should be extensively refined or replaced by robust, ML-powered parsing.
async def _extract_transactions_from_text_fallback(text: str, tenant_config: Dict[str, Any]) -> List[Transaction]:
    transactions = []
    lines = text.split('\n')
    
    # Regex to capture Date, Description, Amount, and optional Balance
    # This pattern is an example and will need significant refinement for different bank formats.
    # It attempts to match common patterns like:
    # DD Mon YYYY Description Amount Balance (e.g., 01 Jan 2023 SALARY 1500.00 2000.00)
    # YYYY-MM-DD Description Amount (e.g., 2023-01-01 PAYMENT 100.00)
    # It assumes amounts are formatted like 1,000.00 or 1000.00
    
    # Capture Group 1: Date (flexible formats)
    # Capture Group 2: Description (anything between date and amount)
    # Capture Group 3: Amount (with optional sign, commas, decimal)
    # Capture Group 4: Type (CR/DR) or infer from amount
    # Capture Group 5: Optional Balance
    
    # A more robust approach might look for specific table structures.
    transaction_pattern = re.compile(
        r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|\d{4}-\d{2}-\d{2})\s+" # Date
        r"(.+?)\s+" # Description (non-greedy)
        r"(-?\s*(?:KSh|KES|R|\$)?\s*\d{1,3}(?:,\d{3})*\.\d{2})\s*" # Amount (allowing KSh, R, $, optional sign, commas)
        r"(CR|DR)?\s*" # Optional Transaction Type
        r"((?:KSh|KES|R|\$)?\s*\d{1,3}(?:,\d{3})*\.\d{2})?" # Optional Balance
    )
    
    # Attempt to detect currency symbol from config for better parsing
    currency_symbol = tenant_config.get("currency_preference", "KES").upper()

    for line in lines:
        match = transaction_pattern.search(line.strip())
        if match:
            date_str, desc, amount_raw, type_hint, balance_raw = match.groups()
            
            # Clean and parse amount
            amount_str = re.sub(r'[^0-9.-]', '', amount_raw.replace(',', '')).strip()
            amount_value = float(amount_str) if amount_str else 0.0

            trans_type = 'credit'
            if type_hint and type_hint.upper() == 'DR':
                trans_type = 'debit'
            elif amount_value < 0: # If no explicit type, infer from sign
                trans_type = 'debit'
                amount_value = abs(amount_value) # Store as positive
            
            balance_value = None
            if balance_raw:
                balance_value = float(re.sub(r'[^0-9.-]', '', balance_raw.replace(',', '')).strip())
            
            # Basic date parsing (needs more robust handling for varied formats)
            try:
                if '-' in date_str: # YYYY-MM-DD
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                else: # DD Mon YYYY
                    parsed_date = datetime.strptime(date_str, '%d %b %Y').strftime('%Y-%m-%d')
            except ValueError:
                parsed_date = date_str # Keep raw if unable to parse

            transactions.append(Transaction(
                date=parsed_date,
                description=desc.strip(),
                amount=amount_value,
                type=trans_type,
                balance_after=balance_value,
                original_currency=currency_symbol
            ))
    return transactions