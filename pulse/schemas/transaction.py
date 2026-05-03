"""
Pulse Transaction Schemas — Pydantic data contracts.

These schemas define the strict data structures exchanged between
LangGraph nodes. The LLM must output data conforming to `TransactionInput`;
the database returns data conforming to `TransactionRecord`.

This is the "Tool-First Design" principle from the spec:
    → Never let the LLM hallucinate a database entry.
    → All writes go through Pydantic-validated structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionInput(BaseModel):
    """
    Structured data extracted from a user's raw text by the Scribe node.

    This schema is what the LLM must produce. It is validated before
    any database write occurs.
    """

    amount: float = Field(
        ...,
        gt=0,
        description="Transaction amount in INR. Must be positive.",
    )
    currency: str = Field(
        default="INR",
        max_length=8,
        description="Currency code. Default: INR.",
    )
    vendor: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Vendor or merchant name.",
    )
    category: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Expense category (e.g., Food, Sport, Transport).",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional user-provided note or context.",
    )
    needs_research: bool = Field(
        default=False,
        description="Set to true if the vendor is a specific brand/company that you do not instantly recognize, or if the category is just a guess.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "amount": 450.0,
                "currency": "INR",
                "vendor": "Badminton Court",
                "category": "Sport",
                "notes": None,
            }
        }
    )


class TransactionRecord(BaseModel):
    """
    Full transaction record as stored in the database.

    Returned by CRUD operations and used for display/analysis.
    """

    id: int
    thread_id: str
    amount: float
    currency: str
    vendor: str
    category: str
    timestamp: datetime
    source_text: str
    is_unusual: bool
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)  # ORM mode: Transaction → TransactionRecord
