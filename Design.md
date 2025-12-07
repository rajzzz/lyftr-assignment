-----

# Lyftr AI Backend Assignment: Design Document

**Date:** 2025-12-07
**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy (Async), SQLite (WAL Mode)

-----

## 1\. High-Level Design (HLD)

### 1.1 System Architecture

The system is designed as a standalone, containerized microservice following the **12-Factor App** methodology. It prioritizes data integrity (exact-once ingestion) and high concurrency (non-blocking reads/writes).

**Architectural Layers:**

1.  **Transport Layer (Uvicorn):** Handles raw HTTP/TCP connections.
2.  **Security Middleware (The Gatekeeper):** Intercepts `POST /webhook` requests. It computes the HMAC-SHA256 signature of the **raw binary body** and validates it against the `X-Signature` header before passing control to the application.
3.  **Application Layer (FastAPI):**
      * **Validation:** Pydantic v2 models ensure payload schema compliance (e.g., `text` length, E.164 phone formats).
      * **Routing:** Dispatches requests to specific handlers (`/webhook`, `/messages`, `/stats`).
4.  **Data Persistence Layer (SQLAlchemy Async):** Manages connection pooling and query construction.
5.  [cite_start]**Storage Engine (SQLite):** A file-based relational database configured in **WAL (Write-Ahead Logging)** mode to allow simultaneous reads and writes[cite: 13, 51, 190].

### 1.2 Data Flow

**A. Write Path (Message Ingestion)**

1.  **Request:** `POST /webhook` arrives with `X-Signature` and JSON body.
2.  **Verify:** Middleware re-computes HMAC. If mismatch $\to$ `401 Unauthorized`.
3.  **Parse:** Pydantic validates schema. If invalid $\to$ `422 Unprocessable Entity`.
4.  **Persist:** System attempts to insert row into DB.
      * [cite_start]*Idempotency Check:* If `message_id` exists (PRIMARY KEY constraint violation), the system catches the error, logs it as a duplicate, and returns `200 OK` to acknowledge receipt[cite: 56, 57].
5.  **Respond:** Returns `{"status": "ok"}`.

**B. Read Path (Analytics & History)**

1.  **Request:** `GET /messages?from=+91...&limit=10`.
2.  [cite_start]**Query:** SQLAlchemy constructs a sanitized SQL `SELECT` statement with `WHERE` clauses for filters and `ORDER BY ts ASC, message_id ASC`[cite: 83].
3.  **IO:** Async driver (`aiosqlite`) fetches data without blocking the event loop.
4.  **Respond:** Returns JSON list with pagination metadata.

-----

## 2\. Low-Level Design (LLD)

### 2.1 Database Schema

**Table Name:** `messages`

| Column Name | Data Type (SQLite) | Python Type | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `message_id` | `TEXT` | `str` | **PK**, Not Null | Unique ID from payload. [cite_start]Used for idempotency[cite: 51]. |
| `from_msisdn` | `TEXT` | `str` | Not Null | Sender number in E.164 format. |
| `to_msisdn` | `TEXT` | `str` | Not Null | Receiver number in E.164 format. |
| `ts` | `TEXT` | `str` | Not Null, **Index** | ISO-8601 UTC timestamp (e.g., `2025-01-15T10:00:00Z`). Indexed for fast range queries. |
| `text` | `TEXT` | `str` | Nullable | Message body (max 4096 chars). |
| `created_at` | `TEXT` | `str` | Not Null | Server-side audit timestamp (UTC). |

### 2.2 Security Logic (HMAC)

The signature verification must occur on the **raw bytes** to avoid parsing discrepancies.

$$
\text{Signature} = \text{HMAC}_{\text{SHA256}}(\text{key}=\text{WEBHOOK\_SECRET}, \text{msg}=\text{Raw HTTP Body})
$$

**Algorithm:**

1.  [cite_start]Retrieve `WEBHOOK_SECRET` from environment variables[cite: 33].
2.  Read `request.body()` as bytes.
3.  Compute `expected_signature = hmac.new(secret, body, sha256).hexdigest()`.
4.  Compare `expected_signature` with `Header['X-Signature']` using `hmac.compare_digest()` to prevent timing attacks.
5.  If valid, proceed. If invalid, abort request immediately.

### 2.3 API Interface Specifications

**Endpoint:** `POST /webhook`

  * **Input Model (`WebhookPayload`):**
    ```python
    from pydantic import BaseModel, Field
    
    class WebhookPayload(BaseModel):
        message_id: str
        from_msisdn: str = Field(alias="from") # Maps JSON "from" to Python variable
        to_msisdn: str = Field(alias="to")
        ts: str
        text: str | None = Field(None, max_length=4096)
    ```
  * [cite_start]**Success Response:** HTTP 200 `{"status": "ok"}`[cite: 55].

**Endpoint:** `GET /messages`

  * **Query Parameters:**
      * `limit`: int (default 50, max 100)
      * `offset`: int (default 0)
      * `from`: str (optional, exact match)
      * `since`: str (optional, ISO timestamp)
      * `q`: str (optional, text search)
  * **Response Model:**
    ```json
    {
      "data": [ ...list of messages... ],
      "total": 124,
      "limit": 50,
      "offset": 0
    }
    ```

-----

## 3\. Project Structure

[cite_start]The repository matches the deliverable requirements[cite: 205].

```text
/app
├── config.py           # Env loading (pydantic-settings)
├── main.py             # FastAPI app & Routes
├── models.py           # Pydantic Schemas & DB Table
├── storage.py          # SQLAlchemy Engine & Init
├── logging_utils.py    # JSON Log Formatter
/tests
├── test_webhook.py
├── test_messages.py
├── test_stats.py
├── Dockerfile          # Multi-stage Python build
├── docker-compose.yml  # Service definition
└── Makefile            # Make up/down/test shortcuts
```

-----

### Generate this as a PDF

If you want this exact text in a PDF file, run this Python script on your machine:

```python
# Save this as generate_pdf.py and run: python generate_pdf.py
# Requires: pip install fpdf
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Lyftr AI Backend Assignment - Design Document', 0, 1, 'C')
        self.ln(10)

pdf = PDF()
pdf.add_page()
pdf.set_font("Arial", size=12)

content = """
1. HIGH-LEVEL DESIGN (HLD)

1.1 Architecture
- Framework: FastAPI (Async)
- Database: SQLite with WAL Mode enabled for concurrency.
- Security: Custom Middleware for HMAC-SHA256 signature verification.

1.2 Data Flow
- Ingestion: Request -> HMAC Check -> Pydantic Validation -> DB Insert (Ignore Duplicates).
- Retrieval: Request -> SQL Select (Indexed by TS) -> JSON Response.

2. LOW-LEVEL DESIGN (LLD)

2.1 Database Schema (Table: messages)
- message_id (PK, TEXT): Unique ID.
- from_msisdn (TEXT): Sender.
- to_msisdn (TEXT): Receiver.
- ts (TEXT): ISO-8601 Timestamp (Indexed).
- text (TEXT): Message content.

2.2 Security Algorithm
- Compute hex digest of HMAC-SHA256(secret, raw_body).
- Compare with X-Signature header using constant-time comparison.

2.3 API Models
- Input: WebhookPayload (Validates length, types, aliases 'from' field).
- Output: MessageResponse (Standard JSON structure).
"""

pdf.multi_cell(0, 10, content)
pdf.output("Lyftr_Design_Doc.pdf")
print("PDF generated successfully: Lyftr_Design_Doc.pdf")
```
