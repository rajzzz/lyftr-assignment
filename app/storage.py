from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from app.config import settings

# 1. Create the Async Engine
# poolclass=NullPool is safer for SQLite in Docker to avoid "database is locked" errors
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=True
)

# 2. Create the Session Factory
# We use this in our FastAPI routes to get a database connection
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """
    Runs on application startup.
    1. Enables WAL mode for concurrency.
    2. Creates tables if they don't exist.
    """
    async with engine.begin() as conn:
        # Enable Write-Ahead Logging (WAL) - CRITICAL for concurrency
        _ = await conn.execute(text("PRAGMA journal_mode=WAL;"))
        # Set a timeout so it waits before failing if DB is busy
        _ = await conn.execute(text("PRAGMA busy_timeout=5000;"))
        
        # Import models here to ensure they are registered with SQLAlchemy
        from app.models import Base
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """
    FastAPI Dependency.
    Yields a DB session and closes it automatically after the request.
    """
    async with AsyncSessionLocal() as session:
        yield session
