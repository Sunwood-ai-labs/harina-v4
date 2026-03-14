from __future__ import annotations

from pydantic import BaseModel, Field


class ReceiptLineItem(BaseModel):
    name: str | None = None
    category: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None

    def has_meaningful_data(self) -> bool:
        return any(
            value not in (None, "")
            for value in (self.name, self.category, self.quantity, self.unit_price, self.total_price)
        )


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
