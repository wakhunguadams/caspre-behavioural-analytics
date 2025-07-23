from motor.motor_asyncio import AsyncIOMotorClient
from databases import Database
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from contextlib import asynccontextmanager
import asyncio # Import asyncio for async operations

from app.core.config import settings

# --- MongoDB Setup ---
mongo_client: AsyncIOMotorClient = None

async def connect_to_mongo():
    global mongo_client
    mongo_client = AsyncIOMotorClient(settings.MONGO_DB_URI)
    try:
        await mongo_client.admin.command('ping')
        print("Connected to MongoDB!")
    except Exception as e:
        print(f"Could not connect to MongoDB: {e}")

async def close_mongo_connection():
    global mongo_client
    if mongo_client:
        mongo_client.close()
        print("MongoDB connection closed.")

def get_mongo_db():
    return mongo_client[settings.MONGO_DB_NAME]

# --- MySQL Setup (for structured data, tenant config, feature store) ---
# Initialize the 'databases' library connection
database = Database(settings.DATABASE_URL)

# SQLAlchemy MetaData for ORM table definitions
metadata = MetaData()

# Base class for SQLAlchemy ORM models (for creating tables if needed)
Base = declarative_base()

# Dependency for MySQL database connection
async def get_db_connection():
    """FastAPI dependency to provide a database connection."""
    yield database

# Function to create tables based on SQLAlchemy models
async def create_mysql_tables():
    """Creates tables for all models defined with Base.metadata if they don't exist.
    This should be run as a separate migration step in production, not on every app startup.
    """
    print("Attempting to create MySQL tables...")
    # Use synchronous engine for create_all; Databases handles async for queries
    # Replace '+aiomysql' with '' to get the base driver for create_engine
    sync_engine = create_engine(settings.DATABASE_URL.replace("+aiomysql", ""), echo=False)
    
    # Run in a separate thread to not block the event loop
    await asyncio.to_thread(Base.metadata.create_all, sync_engine)
    print("MySQL tables ensured.")


# --- Lifespan Events for FastAPI ---
@asynccontextmanager
async def lifespan(app):
    """
    FastAPI lifespan context manager for database connections.
    Connects to MongoDB and MySQL on startup, closes on shutdown.
    """
    await connect_to_mongo()
    await database.connect()
    
    # IMPORTANT: In production, use a proper migration tool like Alembic
    # to manage your database schema. Running create_mysql_tables() on
    # every startup is for quick development setup only and can cause issues.
    # await create_mysql_tables() # Uncomment ONLY for dev/initial setup if no migrations

    print("Database connections established.")
    yield
    await close_mongo_connection()
    await database.disconnect()
    print("Database connections closed.")