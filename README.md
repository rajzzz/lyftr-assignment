# Lyftr AI Backend Assignment

This is a production-style FastAPI service that ingests and serves WhatsApp-like messages.

## Setup Used

- NeoVim + Gemini CLI

## How to Run

1.  **Set up environment variables:**

    Create a `.env` file from the example:
    ```bash
    cp .env.example .env
    ```
    Make sure `WEBHOOK_SECRET` is set to a secure secret in the `.env` file.

2.  **Start the service:**

    The service is containerized using Docker. Use the provided Makefile to start the application.
    ```bash
    make up
    ```
    The API will be available at `http://localhost:8000`.

3.  **Check the logs:**
    ```bash
    make logs
    ```

4.  **Stop the service:**
    ```bash
    make down
    ```

## How to Hit the Endpoints

The base URL for the API is `http://localhost:8000`.

### Health Checks

-   **Liveness Probe:**
    ```bash
    curl http://localhost:8000/health/live
    ```

-   **Readiness Probe:**
    ```bash
    curl http://localhost:8000/health/ready
    ```

### `POST /webhook`

This endpoint ingests a message. It requires a valid `X-Signature` header.

```bash
# Set environment variables for the example
export WEBHOOK_SECRET=$(grep WEBHOOK_SECRET .env | cut -d '=' -f2)
export BODY='{"message_id":"msg_123","from":"+919876543210","to":"+14155550100","ts":"2025-12-07T12:00:00Z","text":"Hello from curl!"}'

# Calculate the signature
export SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')

# Send the request
curl -v -X POST http://localhost:8000/webhook \
-H "Content-Type: application/json" \
-H "X-Signature: $SIGNATURE" \
-d "$BODY"
```

### `GET /messages`

This endpoint lists stored messages with pagination and filtering.

-   **List all messages (with defaults):**
    ```bash
    curl "http://localhost:8000/messages" | jq
    ```

-   **Pagination (`limit` and `offset`):**
    ```bash
    curl "http://localhost:8000/messages?limit=5&offset=1" | jq
    ```

-   **Filter by sender (`from`):**
    ```bash
    curl "http://localhost:8000/messages?from=+919876543210" | jq
    ```

-   **Filter by timestamp (`since`):**
    ```bash
    curl "http://localhost:8000/messages?since=2025-12-07T11:00:00Z" | jq
    ```

-   **Free-text search (`q`):**
    ```bash
    curl "http://localhost:8000/messages?q=Hello" | jq
    ```

### `GET /stats`

This endpoint provides analytics about the stored messages.

```bash
curl http://localhost:8000/stats | jq
```

### `GET /metrics`

This endpoint exposes Prometheus-style metrics (optional, but implemented).

```bash
curl http://localhost:8000/metrics
```

## Design Decisions

### HMAC Signature Verification

-   **Implementation:** HMAC verification is implemented as a FastAPI middleware (`app/main.py`). For every incoming `POST /webhook` request, the middleware reads the raw request body.
-   **Security:** It computes the HMAC-SHA256 hash of the body using the `WEBHOOK_SECRET` from the environment. To prevent timing attacks, the calculated signature is compared against the one in the `X-Signature` header using `hmac.compare_digest()`.
-   **Rationale:** Placing this logic in a middleware ensures that no insecure request ever reaches the application logic. Reading the raw body is crucial because any modification (like JSON parsing) would invalidate the signature.

### Pagination

-   **Contract:** The `GET /messages` endpoint uses `limit` and `offset` for pagination, a standard and widely understood pattern.
-   **Response:** The response includes a `total` field, which communicates the total number of records matching the filter criteria, regardless of the pagination `limit`. This allows clients to build accurate pagination UI (e.g., "Showing 1-50 of 123").
-   **Defaults:** It uses sensible defaults (`limit=50`, `offset=0`) to make the API easy to use.

### Statistics (`/stats`) and Metrics (`/metrics`)

-   **/stats:** The `/stats` endpoint is designed to provide application-level analytics. It computes statistics like total messages, unique senders, and top senders directly via targeted and efficient SQLAlchemy queries against the database. This provides a quick, real-time snapshot of the data.
-   **/metrics:** The `/metrics` endpoint is implemented using `prometheus-fastapi-instrumentator`. It exposes standard Prometheus metrics for request latency, counts, and errors, labeled by path and status code. This is intended for operational monitoring and alerting on the health of the service itself, rather than the data it contains.
