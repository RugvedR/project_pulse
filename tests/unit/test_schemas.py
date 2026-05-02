"""
Unit tests for pulse.schemas.transaction — Pydantic schema validation.

Tests that TransactionInput correctly validates and rejects data.
"""

from __future__ import annotations

import pytest

from pulse.schemas.transaction import TransactionInput, TransactionRecord


class TestTransactionInput:
    """Tests for the TransactionInput schema."""

    def test_valid_minimal_input(self):
        t = TransactionInput(
            amount=450.0,
            vendor="Badminton Court",
            category="Sport",
        )
        assert t.amount == 450.0
        assert t.currency == "INR"  # Default
        assert t.vendor == "Badminton Court"
        assert t.category == "Sport"
        assert t.notes is None

    def test_valid_with_all_fields(self):
        t = TransactionInput(
            amount=350.0,
            currency="USD",
            vendor="Starbucks",
            category="Food",
            notes="Iced latte",
        )
        assert t.currency == "USD"
        assert t.notes == "Iced latte"

    def test_rejects_zero_amount(self):
        with pytest.raises(Exception):  # Pydantic ValidationError
            TransactionInput(
                amount=0,
                vendor="Test",
                category="Food",
            )

    def test_rejects_negative_amount(self):
        with pytest.raises(Exception):
            TransactionInput(
                amount=-100,
                vendor="Test",
                category="Food",
            )

    def test_rejects_empty_vendor(self):
        with pytest.raises(Exception):
            TransactionInput(
                amount=100,
                vendor="",
                category="Food",
            )

    def test_rejects_empty_category(self):
        with pytest.raises(Exception):
            TransactionInput(
                amount=100,
                vendor="Test",
                category="",
            )

    def test_json_serialization_roundtrip(self):
        original = TransactionInput(
            amount=450.0,
            vendor="Badminton Court",
            category="Sport",
        )
        json_str = original.model_dump_json()
        restored = TransactionInput.model_validate_json(json_str)
        assert original == restored

    def test_dict_conversion(self):
        t = TransactionInput(
            amount=450.0,
            vendor="Badminton Court",
            category="Sport",
        )
        d = t.model_dump()
        assert isinstance(d, dict)
        assert d["amount"] == 450.0
        assert d["currency"] == "INR"


class TestTransactionRecord:
    """Tests for the TransactionRecord schema (ORM compatibility)."""

    def test_from_dict(self):
        from datetime import datetime, timezone

        r = TransactionRecord(
            id=1,
            thread_id="user_1",
            amount=450.0,
            currency="INR",
            vendor="Badminton Court",
            category="Sport",
            timestamp=datetime.now(timezone.utc),
            source_text="Spent 450 at the badminton court",
            is_unusual=False,
        )
        assert r.id == 1
        assert r.thread_id == "user_1"
