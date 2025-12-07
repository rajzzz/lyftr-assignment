from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text
from pydantic import BaseModel, Field

# --- PART 1: Database Table (SQLAlchemy) ---
class Base(DeclarativeBase):
    pass

class Message(Base):
    """
    Represents the 'messages' table in SQLite.
    Matches the Minimal Data Model requirement exactly.
    """
    __tablename__: str= "messages"

    # Primary Key is a string (message_id), not an integer
    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    
    from_msisdn: Mapped[str] = mapped_column(String, nullable=False)
    to_msisdn: Mapped[str] = mapped_column(String, nullable=False)
    
    # Store timestamps as ISO Strings to maintain SQLite compatibility
    # Index=True speeds up the "since" filter in GET /messages
    ts: Mapped[str] = mapped_column(String, nullable=False, index=True) 
    
    # Text is optional (nullable)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Audit field: When did WE receive it? (Not when user sent it)
    created_at: Mapped[str] = mapped_column(
        String, 
        default=lambda: datetime.utcnow().isoformat() + "Z"
    )

# --- PART 2: API Validation (Pydantic) ---

class WebhookPayload(BaseModel):
    """
    Validates the incoming JSON from the POST /webhook request.
    """
    message_id: str = Field(min_length=1) # Must not be empty
    
    # "from" is a reserved keyword in Python (like 'import' or 'def').
    # We use 'alias' so the JSON can have "from", but Python sees "from_msisdn".
    from_msisdn: str = Field(
        alias="from", 
        pattern=r"^\+[1-9]\d{1,14}$" # E.164 format
    ) 
    to_msisdn: str = Field(
        alias="to", 
        pattern=r"^\+[1-9]\d{1,14}$" # E.164 format
    )
    
    ts: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$") # ISO-8601 UTC format
    
    # Optional text, max 4096 characters
    text: str | None = Field(default=None, max_length=4096)

class MessageResponse(BaseModel):
    """
    Defines what the GET /messages endpoint returns to the user.
    """
    model_config = {"from_attributes": True}

    message_id: str
    
    # When sending JSON OUT, we map it back to "from" and "to"
    from_msisdn: str = Field(serialization_alias="from")
    to_msisdn: str = Field(serialization_alias="to")
    
    ts: str
    text: str | None
