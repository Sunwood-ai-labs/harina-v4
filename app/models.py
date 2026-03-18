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


class ReceiptGeminiUsage(BaseModel):
    model: str
    request_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    estimated_input_cost_usd: float | None = None
    estimated_output_cost_usd: float | None = None
    estimated_total_cost_usd: float | None = None


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
    gemini_usage: ReceiptGeminiUsage | None = None


class ReceiptLineItemCategoryAssignment(BaseModel):
    item_index: int
    category: str | None = None


class ReceiptCategoryInference(BaseModel):
    line_items: list[ReceiptLineItemCategoryAssignment] = Field(default_factory=list)
