from typing import Callable, Annotated, Awaitable
import time
import uuid
import hmac
import hashlib
import logging

from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError

from prometheus_fastapi_instrumentator import PrometheusFastApiInstrumentator
from prometheus_client import Counter

from app.config import settings
from app.storage import get_db, init_db
from app.logging_utils import setup_logging
from app.models import Message, WebhookPayload, MessageResponse

# 1. Setup Logging immediately
setup_logging()
logger = logging.getLogger("api")

# --- METRICS COUNTER ---
WEBHOOK_REQUESTS_TOTAL = Counter(
    "webhook_requests_total",
    "Total number of webhook requests by result",
    ["result"]
)

# --- Lifespan + app creation ---
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    if not settings.WEBHOOK_SECRET:
        logger.critical("WEBHOOK_SECRET is not set! Exiting.")
        raise SystemExit(1)


    # Ensure DB is ready / create tables
    await init_db()
    logger.info("Application startup complete.")
    
    yield  # 👈 Application runs normally after this line

    # --- Shutdown ---
    logger.info("Application shutting down.")

# Instrument the app and expose the /metrics endpoint

app = FastAPI(title="Lyftr AI Webhook Service", lifespan=lifespan)

PrometheusFastApiInstrumentator().instrument(app).expose(app)

# --- Custom Exception Handler for Validation Errors ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Only count validation errors for the /webhook endpoint
    if request.url.path == "/webhook":
        WEBHOOK_REQUESTS_TOTAL.labels(result="validation_error").inc()
    return await request_validation_exception_handler(request, exc)


# --- MIDDLEWARE (JSON logging + request_id) ---
@app.middleware("http")
async def log_request_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    Wraps every request to log structured JSON data.
    Captures: ts, level, request_id, method, path, status, latency_ms.
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()
    
    response: Response
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        # log full traceback
        logger.exception("Request failed", extra={"request_id": request_id})
        status_code = 500
        response = JSONResponse(content={"detail": "Internal Server Error"}, status_code=500)

    # Calculate latency
    process_time = time.time() - start_time
    latency_ms = round(process_time * 1000, 2)
    
    # LOG THE DATA (This hits your JSONFormatter in logging_utils.py)
    logger.info(
        "Request processed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": status_code,
            "latency_ms": latency_ms
        }
    )
    
    return response


# --- HMAC VERIFICATION DEPENDENCY ---
async def verify_signature(request: Request) -> None:
    """
    Validates X-Signature header against the RAW body bytes.
    """
    signature = request.headers.get("X-Signature")
    if not signature:
        WEBHOOK_REQUESTS_TOTAL.labels(result="invalid_signature").inc()
        raise HTTPException(status_code=401, detail="invalid signature")
    
    # 1. Read the raw bytes (Important: Do not use await request.json() here!)
    body_bytes = await request.body()
    
    # 2. Compute expected HMAC
    expected_sig = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # 3. Secure comparison (prevents timing attacks)
    if not hmac.compare_digest(signature, expected_sig):
        WEBHOOK_REQUESTS_TOTAL.labels(result="invalid_signature").inc()
        raise HTTPException(status_code=401, detail="invalid signature")
    
    # If valid, allow request to continue
    return None


# --- WEBHOOK ENDPOINT ---
@app.post("/webhook", dependencies=[Depends(verify_signature)])
async def receive_webhook(
    payload: WebhookPayload, 
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests messages. Idempotent based on message_id.
    """
    new_msg = Message(
        message_id=payload.message_id,
        from_msisdn=payload.from_msisdn,
        to_msisdn=payload.to_msisdn,
        ts=payload.ts,
        text=payload.text
    )
    
    try:
        db.add(new_msg)
        await db.commit()
        
        WEBHOOK_REQUESTS_TOTAL.labels(result="created").inc()
        logger.info(
            "Webhook ingested",
            extra={
                "message_id": payload.message_id,
                "dup": False,
                "result": "created"
            }
        )
        return {"status": "ok"}
        
    except IntegrityError:
        # IDEMPOTENCY HANDLER
        await db.rollback()
        
        WEBHOOK_REQUESTS_TOTAL.labels(result="duplicate").inc()
        logger.warning(
            "Duplicate webhook received",
            extra={
                "message_id": payload.message_id,
                "dup": True,
                "result": "duplicate"
            }
        )
        return {"status": "ok"}


# --- 1. GET /messages (Pagination + Filtering) ---
@app.get("/messages", response_model=dict)
async def list_messages(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    from_msisdn: Annotated[str | None, Query(alias="from")] = None,
    since: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List messages with filters. 
    Ordering: ts ASC, message_id ASC.
    """
    # 1. Base query
    query = select(Message)
    
    # 2. Filters
    if from_msisdn:
        query = query.where(Message.from_msisdn == from_msisdn)
    if since:
        query = query.where(Message.ts >= since)
    if q:
        query = query.where(Message.text.ilike(f"%{q}%"))

    # 3. Count using same filters (safer than subquery of full query)
    count_query = select(func.count()).select_from(Message)
    if from_msisdn:
        count_query = count_query.where(Message.from_msisdn == from_msisdn)
    if since:
        count_query = count_query.where(Message.ts >= since)
    if q:
        count_query = count_query.where(Message.text.ilike(f"%{q}%"))

    total_result = await db.execute(count_query)
    total = total_result.scalar_one() or 0

    # 4. Ordering & pagination
    query = query.order_by(Message.ts.asc(), Message.message_id.asc()).limit(limit).offset(offset)

    # 5. Execute
    result = await db.execute(query)
    messages = result.scalars().all()  # list[Message]

    # 6. Convert ORM -> Pydantic dicts (Pydantic v2: model_validate + model_dump)
    # Make sure MessageResponse.model_config = {"from_attributes": True}
    data = [MessageResponse.model_validate(m, from_attributes=True).model_dump(by_alias=True) for m in messages]

    return {
        "data": data,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# --- 2. GET /stats (Analytics) ---
@app.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """
    Simple analytics: Total count, top senders, time range.
    """
    # Total messages
    total_query = select(func.count(Message.message_id))
    total_res = await db.execute(total_query)
    total_messages = total_res.scalar_one() or 0

    # Unique senders
    senders_query = select(func.count(func.distinct(Message.from_msisdn)))
    senders_res = await db.execute(senders_query)
    senders_count = senders_res.scalar_one() or 0

    # Top senders
    top_senders_query = (
        select(Message.from_msisdn, func.count(Message.message_id).label("count"))
        .group_by(Message.from_msisdn)
        .order_by(desc(func.count(Message.message_id)))
        .limit(10)
    )
    top_senders_res = await db.execute(top_senders_query)
    messages_per_sender = [{"from": row[0], "count": row[1]} for row in top_senders_res.all()]

    # Min / Max timestamps (safe if empty)
    min_max_query = select(func.min(Message.ts).label("min_ts"), func.max(Message.ts).label("max_ts"))
    min_max_res = await db.execute(min_max_query)
    min_row = min_max_res.one_or_none()
    if min_row is None:
        min_ts = None
        max_ts = None
    else:
        min_ts, max_ts = min_row[0], min_row[1]

    return {
        "total_messages": total_messages,
        "senders_count": senders_count,
        "messages_per_sender": messages_per_sender,
        "first_message_ts": min_ts,
        "last_message_ts": max_ts
    }

@app.get("/health/live")
async def liveness():
    """Always returns 200 if app is running."""
    return {"status": "ok"}

@app.get("/health/ready")
async def readiness():
    """
    Returns 200 only if DB is reachable and Secret is set.
    """
    if not settings.WEBHOOK_SECRET:
        return JSONResponse(status_code=503, content={"detail": "Secret missing"})
    
    # In a real app, we might check DB connectivity here too
    return {"status": "ready"}
