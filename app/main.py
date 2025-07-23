from fastapi import FastAPI
from app.api.v2.endpoints import router as api_router
from app.core.config import settings
from app.core.db import lifespan as db_lifespan_event
from app.core.messaging import get_kafka_producer, close_kafka_producer
from contextlib import asynccontextmanager

# Combine lifespans for database and messaging
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Call database lifespan events (connect/disconnect)
    async with db_lifespan_event(app):
        # Initialize Kafka producer
        await get_kafka_producer()
        print("Application startup complete.")
        yield
        # Close Kafka producer
        await close_kafka_producer()
        print("Application shutdown complete.")

app = FastAPI(
    title=settings.APP_NAME,
    description="Behavioral Analytics Microservice: Processes bank statements, extracts features, calculates scores, and generates insights.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan # Assign the combined lifespan here
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", summary="Root endpoint for service health check")
async def root():
    """
    Returns a simple message indicating the service is running.
    """
    return {"message": "Behavioral Analytics Service is running. Access API at /api/v1/docs"}