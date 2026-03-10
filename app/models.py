from __future__ import annotations

from pydantic import BaseModel, Field


class ReceiptLineItem(BaseModel):
    name: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None


class ReceiptExtraction(BaseModel):
    merchant_name: str | None = None
    merchant_phone: str | None = None
    purchase_date: str | None = None
    purchase_time: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    payment_method: str | None = None
    receipt_number: str | None = None
    language: str | None = None
    notes: str | None = None
    confidence: float | None = None
    raw_text: str | None = None
    line_items: list[ReceiptLineItem] = Field(default_factory=list)
