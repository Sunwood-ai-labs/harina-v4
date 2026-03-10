import { describe, expect, it } from "vitest";

import type { ReceiptExtraction } from "../src/receipt-schema.js";
import { buildDriveFileName, formatReceiptSummary } from "../src/utils/receipt-format.js";

const sampleExtraction: ReceiptExtraction = {
  merchantName: "Cafe Harina",
  merchantPhone: null,
  purchaseDate: "2026-03-11",
  purchaseTime: null,
  currency: "JPY",
  subtotal: 1000,
  tax: 100,
  total: 1100,
  paymentMethod: "VISA",
  receiptNumber: "12345",
  language: "ja",
  notes: null,
  confidence: 0.94,
  rawText: null,
  lineItems: []
};

describe("buildDriveFileName", () => {
  it("uses merchant and date in the generated file name", () => {
    expect(buildDriveFileName("photo 1.jpg", sampleExtraction)).toContain("2026-03-11_Cafe-Harina");
  });
});

describe("formatReceiptSummary", () => {
  it("includes merchant, total, date, and drive url", () => {
    expect(formatReceiptSummary(sampleExtraction, "https://drive.example/file")).toBe(
      "Cafe Harina | 1100 JPY | 2026-03-11 | Drive: https://drive.example/file"
    );
  });
});
