Behavioral Analytics Microservice
Table of Contents
Overview

Features

Architecture

Technologies Used

Setup and Installation

Prerequisites

Environment Variables (.env)

Database Setup (MySQL & MongoDB)

Kafka Setup

Cloud Provider Setup (GCP / AWS)

Installation Steps

Running the Application

API Endpoints

Asynchronous Processing (Kafka)

Tenant-Specific Configuration

Extensibility and Customization

Future Enhancements

Contributing

License

1. Overview
The Behavioral Analytics Microservice is a core component of a larger financial ecosystem, designed to ingest, process, and analyze customer bank statements to derive valuable behavioral insights and a comprehensive behavioral score. This service automates the extraction of financial data, identifies spending patterns, income stability, debt servicing capacity, and detects anomalies, ultimately providing a holistic view of an individual's financial behavior.

This microservice is built with scalability, extensibility, and multi-tenancy in mind, allowing for custom configurations per financial institution (tenant) and integrating seamlessly with other services via asynchronous messaging.

2. Features
Bank Statement Ingestion: Accepts PDF, JPG, and PNG bank statements.

Intelligent Document Processing (IDP): Extracts structured transaction data from unstructured bank statements using cloud-based IDP services (Google Document AI / AWS Textract) with a fallback to rule-based text extraction.

Financial Feature Engineering: Transforms raw transactions into meaningful financial metrics and indicators (e.g., average monthly income, spending-to-income ratio, savings rate, categorized spending).

Transaction Categorization: Automatically categorizes transactions based on configurable rules, supporting tenant-specific customization.

Behavioral Scoring: Calculates a quantitative behavioral score based on engineered features and pre-defined rules/weights.

Anomaly Detection: Identifies unusual or suspicious transaction patterns.

Explainable AI (XAI): Provides insights into the factors influencing the behavioral score using SHAP values.

LLM-Powered Insights: Generates human-readable narrative summaries of financial behavior using large language models (Google Gemini), with configurable tone and content.

Asynchronous Processing: Utilizes Kafka for decoupled and scalable processing of bank statements.

Multi-Tenancy: Supports different financial institutions (tenants) with customizable rules, weights, and LLM tone.

Cloud Storage Integration: Stores raw and processed bank statements securely in Google Cloud Storage (GCS) or AWS S3.

API Interface: Provides RESTful API endpoints for file upload, job status tracking, and results retrieval.

3. Architecture
The Behavioral Analytics Microservice is designed with a microservices-oriented architecture pattern, leveraging asynchronous communication and cloud-native services.

Code snippet

graph TD
    A[API Gateway] --> B(FastAPI Behavioral Analytics Microservice)
    B -- Upload File --> C(Cloud Storage: GCS / S3)
    B -- Queue Job --> D[Kafka Topic: bank_statement_uploads]
    D --> E(Kafka Consumer Worker - Internal to Microservice)
    E -- Process with --> F(IDP Service: Google Doc AI / AWS Textract)
    F --> G(Feature Engineering Module)
    G --> H(Behavioral Scoring Module)
    H --> I(LLM Insights Module: Google Gemini)
    I -- Store Results --> J(MongoDB: analytics_results)
    I -- Log Processing --> J
    J <-- Retrieve Results --> B
    B -- Publish Results --> K[Kafka Topic: analytics_results]
    B -- Callbacks (Optional) --> L(External Callback Service)
    B -- Tenant Config --> M(MySQL: tenant_configurations)
Key Components & Data Flow:

Client/API Gateway: Initiates the process by sending a bank statement file and metadata to the microservice.

FastAPI Microservice (Primary API):

Receives file uploads.

Validates input and extracts X-Company-ID and X-Customer-ID headers.

Uploads the raw bank statement file to secure Cloud Storage (GCS/S3).

Creates an asynchronous processing job and pushes it to a Kafka topic (bank_statement_uploads).

Returns a job_id for status tracking.

Kafka Consumer Worker (Internal to Microservice):

Continuously listens to the bank_statement_uploads topic.

Picks up new jobs and triggers the analytical pipeline.

Analytical Pipeline:

IDP Processor: Downloads the file from cloud storage and sends it to the configured IDP Service (Google Document AI / AWS Textract) to extract structured transaction data. A fallback basic text parsing is included.

Feature Engineer: Takes extracted transactions and computes rich financial features (e.g., income stability, spending categories, balance trends) and performs rule-based anomaly detection.

Behavioral Scoring Model: Uses the engineered features to calculate a behavioral score, applying tenant-specific weights and rules. Provides SHAP-based explanations for score drivers.

LLM Insights Generator: Leverages Google Gemini to create a human-readable narrative summary of the customer's financial behavior, incorporating key metrics, anomalies, and the overall score, adapting to tenant-defined tone guidelines.

Databases:

MongoDB: Stores the full analytics results, including categorized transactions, key metrics, anomalies, and LLM insights, associated with the job_id. Also used for logging processing errors.

MySQL: Stores structured tenant-specific configurations (e.g., categorization rules, scoring weights, LLM tone guidelines).

Kafka (analytics_results topic): After successful processing, a notification is sent to this topic, allowing other downstream services (e.g., Credit Scoring, Agent Orchestration, Frontend Dashboard) to react to the completed analysis.

Callbacks (Optional): If a callback_url is provided in the initial request, the microservice attempts to send a POST request to that URL upon job completion or failure.

4. Technologies Used
Python 3.9+: The primary programming language.

FastAPI: High-performance web framework for building APIs.

Pydantic: Data validation and settings management.

SQLAlchemy: ORM for interacting with MySQL.

Databases: Asynchronous SQL toolkit for FastAPI (aiomysql driver).

Motor: Asynchronous MongoDB driver.

Kafka-Python: Python client for Apache Kafka.

Pandas & NumPy: Data manipulation and numerical operations for feature engineering.

Scikit-learn / XGBoost: Machine learning libraries for behavioral scoring (placeholder model).

SHAP: Explainable AI library for score explanations.

Google Cloud Storage (GCS) / AWS S3: Cloud object storage for bank statements.

Google Cloud Document AI / AWS Textract: Cloud-based Intelligent Document Processing.

Google Gemini API: Large Language Model for generating insights.

Docker / Docker Compose: For local development environment setup (databases, Kafka).

5. Setup and Installation
Prerequisites
Before you begin, ensure you have the following installed:

Python 3.9+

pip (Python package installer)

Docker and Docker Compose (for running MySQL, MongoDB, and Kafka locally)

Google Cloud SDK (if using GCP services)

AWS CLI (if using AWS services)

Environment Variables (.env)
Create a .env file in the root directory of the behavioral_analytics_service project. Populate it with your specific configurations.

Ini, TOML

# --- Database Configuration ---
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password_here
MYSQL_SERVER=localhost
MYSQL_PORT=3306
MYSQL_DB=behavioral_analytics_db

MONGO_DB_URI=mongodb://localhost:27017/ # For local Docker setup
MONGO_DB_NAME=bank_statements_db

# --- Cloud Storage Configuration ---
# Choose either GCS or AWS_S3. Uncomment and configure the relevant section.
CLOUD_STORAGE_PROVIDER=GCS # Or AWS_S3

# If CLOUD_STORAGE_PROVIDER=GCS:
GCS_BUCKET_NAME=your-gcs-bucket-name
GCP_PROJECT_ID=your-gcp-project-id
GCP_DOC_AI_PROCESSOR_ID=your-doc-ai-processor-id # Required for GCP Document AI
GCP_DOC_AI_LOCATION=us # e.g., us, eu, africa-south1 (must match Doc AI processor location)

# If CLOUD_STORAGE_PROVIDER=AWS_S3:
AWS_S3_BUCKET_NAME=your-aws-s3-bucket-name
AWS_REGION_NAME=af-south-1 # e.g., us-east-1, eu-west-1, af-south-1

# --- Kafka Configuration ---
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 # For local Docker setup

# --- AI Service Configuration ---
GEMINI_API_KEY=YOUR_GOOGLE_GEMINI_API_KEY # Get from Google AI Studio

# --- Application Specific ---
APP_NAME="Behavioral Analytics Service"
API_V1_STR="/api/v1"
TENANT_AUTH_HEADER="X-Company-ID" # Header name for tenant identification
CUSTOMER_AUTH_HEADER="X-Customer-ID" # Header name for customer identification

# --- Uvicorn (Web Server) Configuration (Optional) ---
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
Database Setup (MySQL & MongoDB)
Use Docker Compose to run local instances of MySQL and MongoDB. Create a docker-compose.yml file in your project root:

YAML

# docker-compose.yml
version: '3.8'

services:
  mysql_db:
    image: mysql:8.0
    container_name: behavioral_analytics_mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_PASSWORD} # Use password from .env
      MYSQL_DATABASE: ${MYSQL_DB} # Use DB name from .env
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 5

  mongodb:
    image: mongo:latest
    container_name: behavioral_analytics_mongodb
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongo localhost:27017/test --quiet
      interval: 5s
      timeout: 5s
      retries: 5

  zookeeper:
    image: confluentinc/cp-zookeeper:7.6.0
    container_name: zookeeper
    ports:
      - "2181:2181"
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    container_name: kafka
    ports:
      - "9092:9092"
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0

volumes:
  mysql_data:
  mongodb_data:
Start the databases and Kafka:

Bash

docker-compose up -d mysql_db mongodb zookeeper kafka
Verify that both mysql_db and mongodb containers are running and healthy (docker ps).

MySQL Table Creation (Initial Development):
For initial development, you can uncomment await create_mysql_tables() in app/core/db.py's lifespan function. For production, use a proper migration tool like Alembic.

Kafka Setup
The docker-compose.yml also includes Kafka and Zookeeper. Once docker-compose up -d is run, Kafka should be available at localhost:9092.

Cloud Provider Setup (GCP / AWS)
Google Cloud Platform (GCP):

Enable APIs: Ensure the "Cloud Storage API" and "Document AI API" are enabled in your GCP project.

Service Account: Create a service account with the following roles:

Storage Object Admin (for bucket access)

Document AI Viewer (for processor access)

Document AI Reader (for reading processed documents)

Authentication:

Recommended (Production): Deploy the service on Google Cloud (e.g., Cloud Run, GKE) where it can use Workload Identity or attached service accounts.

Local Development: Download the service account key (JSON file) and set the GOOGLE_APPLICATION_CREDENTIALS environment variable to its path:

Bash

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
Google Cloud Storage Bucket: Create a bucket (e.g., your-gcs-bucket-name) for storing bank statements.

Document AI Processor:

Go to Document AI in the GCP console.

Create a "Bank Statement Processor" (or similar custom processor if needed). Train it with your bank statement samples for optimal results.

Note down the Processor ID and Location (e.g., us, eu, africa-south1). These go into your .env file.

Google Gemini API: Obtain an API Key from Google AI Studio. Add it to your .env file.

Amazon Web Services (AWS):

Enable Services: AWS S3 and AWS Textract.

IAM User/Role: Create an IAM user or role with permissions for:

s3:PutObject, s3:GetObject on your designated S3 bucket.

textract:StartDocumentAnalysis, textract:GetDocumentAnalysis.

Authentication:

Recommended (Production): Deploy the service on AWS (e.g., EC2, ECS) with an IAM role attached.

Local Development: Configure your AWS CLI with credentials:

Bash

aws configure
S3 Bucket: Create an S3 bucket (e.g., your-aws-s3-bucket-name) for storing bank statements.

AWS Textract: Textract is a service, not a pre-trained model you deploy. It infers structure.

Installation Steps
Clone the repository:

Bash

git clone https://github.com/your-repo/behavioral_analytics_service.git
cd behavioral_analytics_service
Create a virtual environment:

Bash

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies:

Bash

pip install -r requirements.txt
Running the Application
After setting up your .env file and starting Docker services, run the FastAPI application:

Bash

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
The --reload flag is useful for development as it restarts the server on code changes. For production, remove this flag.

The API will be available at http://localhost:8000. You can access the interactive API documentation (Swagger UI) at http://localhost:8000/api/v1/docs.

6. API Endpoints
All API endpoints are prefixed with /api/v1.

1. Upload Bank Statement for Analysis
Endpoint: POST /api/v1/upload-bank-statement
Summary: Upload a bank statement file (PDF, JPG, PNG) to initiate behavioral analysis.
Headers:

X-Company-ID: Your tenant/company identifier.

X-Customer-ID: The customer's unique identifier.
Request Body (Form Data):

file: The bank statement file (e.g., bank_statement.pdf).

callback_url (optional): A URL where the service should send a POST request upon job completion/failure.
Response: 202 Accepted

JSON

{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "QUEUED",
  "message": "Bank statement uploaded and analysis job queued. Use the job_id to check status."
}
2. Get Job Status
Endpoint: GET /api/v1/analytics/status/{job_id}
Summary: Retrieve the current processing status of an analysis job.
Parameters:

job_id (path): The unique ID of the analysis job.
Response: 200 OK (or 404 Not Found if job_id doesn't exist)

JSON

{
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "PROCESSING",
  "message": "Performing feature engineering...",
  "result_url": null # Will be present if status is COMPLETED
}
3. Get Analysis Results
Endpoint: GET /api/v1/analytics/results/{job_id}
Summary: Retrieve the full behavioral analytics results for a completed job.
Parameters:

job_id (path): The unique ID of the analysis job.
Response: 200 OK (or 202 Accepted if still processing, 404 Not Found if job_id invalid, 400 Bad Request if job failed)

JSON

{
  "company_id": "ACME_Bank",
  "customer_id": "CUST12345",
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "completed",
  "behavioral_score": 785.5,
  "score_explanation": {
    "income_consistency": 50.2,
    "avg_monthly_income": 35.1,
    "spending_to_income_ratio": -20.5,
    "total_spending": -10.0,
    // ... other features with their impact on score
  },
  "analysis_summary": "Based on your bank statement for customer CUST12345, you demonstrate strong financial health with consistent income and good savings habits. Your average monthly income is KES 150,000.00, contributing positively to your score. While your spending-to-income ratio is healthy, there was a large debit transaction detected on 2023-05-10 which might warrant review. Your behavioral score of 785.5 reflects a low-risk financial profile...",
  "key_metrics": [
    {
      "name": "Average Monthly Income",
      "value": 150000.0,
      "unit": "KES",
      "description": "Average income received per month."
    },
    {
      "name": "Spending By Category",
      "value": {
        "groceries": 25000.0,
        "rent": 50000.0,
        "transport": 10000.0,
        "Uncategorized": 5000.0
      },
      "description": "Breakdown of spending by categorized types."
    }
    // ... more key metrics
  ],
  "categorized_transactions": [
    {
      "date": "2023-05-01",
      "description": "SALARY DEPOSIT",
      "amount": 150000.0,
      "type": "credit",
      "category": "income",
      "balance_after": 200000.0
    },
    // ... more categorized transactions
  ],
  "anomalies_detected": [
    {
      "type": "Unusually Large Debit",
      "description": "Transaction of KES 50000.00 is significantly larger than typical spending.",
      "transaction": {
        "date": "2023-05-10",
        "description": "Large Purchase",
        "amount": 50000.0,
        "type": "debit"
      },
      "reason": null
    }
    // ... more anomalies
  ],
  "rule_engine_breakdown": [
    {
      "rule_name": "High Savings Rate",
      "condition_met": "Savings Rate (0.15) exceeded 0.1.",
      "adjustment": 20.0,
      "new_score_after_adjustment": 785.5
    }
  ],
  "localization_details": {
    "language": "en",
    "currency": "KES",
    "timezone": "Africa/Nairobi"
  },
  "processed_at": "2023-10-27T10:30:00.123456"
}
4. Update Tenant Configuration
Endpoint: PUT /api/v1/tenant-config/{company_id}
Summary: Updates configuration settings for a specific tenant.
Parameters:

company_id (path): The tenant's identifier.
Headers:

X-Company-ID: Your tenant/company identifier (must match path parameter).

X-Customer-ID: Any valid customer ID (can be placeholder for this endpoint).
Request Body (Form Data with config_updates as JSON string):

config_updates: A JSON string containing the fields to update. Example:

JSON

{
    "language_preference": "sw",
    "transaction_categorization_rules": {
        "m-pesa_deposit": ["m-pesa receive"],
        "groceries": ["supermarket", "grocery", "naivas", "carrefour"]
    },
    "llm_tone_guidelines": {
        "professional": true,
        "concise": true,
        "avoid_jargon": true
    },
    "behavioral_scoring_weights": {
        "high_spending_penalty": 75,
        "high_savings_bonus": 30
    }
}
Response: 200 OK

JSON

{
  "message": "Tenant configuration updated successfully",
  "config": {
    "company_id": "ACME_Bank",
    "language_preference": "sw",
    "currency_preference": "KES",
    // ... updated configuration
  }
}
5. Get Tenant Configuration
Endpoint: GET /api/v1/tenant-config/{company_id}
Summary: Retrieves the configuration settings for a specific tenant.
Parameters:

company_id (path): The tenant's identifier.
Headers:

X-Company-ID: Your tenant/company identifier (must match path parameter).

X-Customer-ID: Any valid customer ID (can be placeholder for this endpoint).
Response: 200 OK

JSON

{
  "message": "Tenant configuration retrieved successfully",
  "config": {
    "company_id": "ACME_Bank",
    "language_preference": "en",
    "currency_preference": "KES",
    "timezone": "Africa/Nairobi",
    "bank_statement_formats": [],
    "transaction_categorization_rules": {
        "income": ["salary", "payroll", "deposit"],
        // ... default or configured rules
    },
    // ... full configuration
  }
}
7. Asynchronous Processing (Kafka)
The microservice leverages Kafka for asynchronous job processing:

Producer: When a bank statement is uploaded via the /upload-bank-statement endpoint, a BehavioralAnalyticsJob message is produced to the bank_statement_uploads Kafka topic.

Consumer: An internal Kafka consumer (simulated in _process_bank_statement_job within endpoints.py for simplicity) listens to this topic. In a production environment, this consumer logic would typically reside in a separate dedicated worker process or microservice to ensure proper resource isolation and scalability.

Results Topic: Upon completion of the analysis, a simplified result notification is published to the analytics_results Kafka topic. This allows other services to subscribe and react to completed analyses without directly polling this service.

8. Tenant-Specific Configuration
The app/utils/tenant_config.py module manages tenant-specific settings stored in MySQL. This allows each financial institution to customize:

Language & Currency Preferences: For localization of insights.

Transaction Categorization Rules: Define keywords for auto-categorization relevant to their market.

Behavioral Scoring Weights: Adjust the importance of various financial features in the final score calculation.

LLM Tone Guidelines: Specify the desired tone (e.g., professional, concise, empathetic) for the AI-generated summaries.

Supported File Types/Sizes: Define operational limits.

New tenants automatically get a default configuration, which can then be updated via the /tenant-config/{company_id} endpoints.

9. Extensibility and Customization
IDP Integration: The idp_processor.py is modular. You can extend it to integrate with other IDP services or improve the rule-based extraction for specific bank statement formats.

Feature Engineering: feature_engineer.py is the place to add more sophisticated financial metrics, derive new behavioral indicators, or implement advanced time-series analysis using libraries like tsfresh.

Scoring Model: scoring_model.py currently uses a dummy XGBoost model. This is where you would load and integrate your actual, production-trained machine learning model for behavioral scoring. You might also incorporate more complex rule engines.

Anomaly Detection: Enhance the anomalies_detected logic in feature_engineer.py with more advanced statistical or machine learning-based anomaly detection techniques.

LLM Insights: Further refine the prompts in llm_insights.py to achieve more nuanced, comprehensive, or tailored narrative summaries based on various financial scenarios.

Callback Mechanism: Enhance the callback_url logic to include retry mechanisms, exponential backoff, and robust error handling for external service communication.

10. Future Enhancements
Dedicated Kafka Consumer Service: Decouple the _process_bank_statement_job into a separate Python service/worker (e.g., using Celery, or a dedicated FastAPI background worker) that solely consumes from Kafka and processes jobs. This would scale independently.

Robust Error Handling & Logging: Implement more comprehensive logging (e.g., using loguru or structlog) and centralized error monitoring.

Authentication & Authorization: Integrate a full-fledged authentication system (e.g., JWT validation) for API access, replacing simple header checks for X-Company-ID and X-Customer-ID.

Database Migrations: Implement Alembic for managing MySQL schema migrations in a robust, version-controlled manner.

Asynchronous Callbacks: Use httpx or aiohttp for non-blocking HTTP requests to callback_url.

Observability: Add metrics (Prometheus/Grafana), tracing (Jaeger/OpenTelemetry), and advanced health checks.

Scalability: Containerize the service for deployment on Kubernetes (GKE, EKS) or serverless platforms (Cloud Run, AWS Lambda).

Performance Optimization: Profile and optimize expensive operations, especially IDP and feature engineering.

More Sophisticated IDP: Integrate with structured output from IDP services (e.g., table parsing) rather than relying heavily on full-text fallback.

Data Masking/PII Handling: Implement robust data masking for sensitive information, especially when logging or storing raw text.

Comprehensive Testing: Add unit, integration, and end-to-end tests.

11. Contributing
Contributions are welcome! Please follow these steps:

Fork the repository.

Create a new branch (git checkout -b feature/your-feature-name).

Make your changes.

Commit your changes (git commit -m 'Add new feature').

Push to the branch (git push origin feature/your-feature-name).

Create a new Pull Request.

12. License
This project is licensed under the MIT License. See the LICENSE file for details.# caspre-behavioural-analytics
