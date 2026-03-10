import { z } from "zod";

const optionalString = z.string().trim().min(1).optional().nullable().transform((value) => value ?? null);
const optionalNumber = z.number().finite().optional().nullable().transform((value) => value ?? null);

export const receiptLineItemSchema = z.object({
  name: optionalString,
  quantity: optionalNumber,
  unitPrice: optionalNumber,
  totalPrice: optionalNumber
});

export const receiptExtractionSchema = z.object({
  merchantName: optionalString,
  merchantPhone: optionalString,
  purchaseDate: optionalString,
  purchaseTime: optionalString,
  currency: optionalString,
  subtotal: optionalNumber,
  tax: optionalNumber,
  total: optionalNumber,
  paymentMethod: optionalString,
  receiptNumber: optionalString,
  language: optionalString,
  notes: optionalString,
  confidence: optionalNumber,
  rawText: optionalString,
  lineItems: z.array(receiptLineItemSchema).optional().default([])
});

export type ReceiptLineItem = z.infer<typeof receiptLineItemSchema>;
export type ReceiptExtraction = z.infer<typeof receiptExtractionSchema>;

export const receiptResponseSchema = {
  type: "object",
  properties: {
    merchantName: { type: "string", description: "Store or merchant name on the receipt." },
    merchantPhone: { type: "string", description: "Phone number on the receipt if present." },
    purchaseDate: {
      type: "string",
      description: "Purchase date in ISO 8601 format when possible, otherwise the original readable form."
    },
    purchaseTime: { type: "string", description: "Purchase time if present." },
    currency: { type: "string", description: "Currency code or symbol such as JPY or USD." },
    subtotal: { type: "number", description: "Subtotal amount before taxes when present." },
    tax: { type: "number", description: "Tax amount when present." },
    total: { type: "number", description: "Grand total amount on the receipt." },
    paymentMethod: { type: "string", description: "Payment method when present." },
    receiptNumber: { type: "string", description: "Receipt or transaction number when present." },
    language: { type: "string", description: "Primary language used on the receipt." },
    notes: { type: "string", description: "Short notes about ambiguity or extra context." },
    confidence: {
      type: "number",
      description: "Extraction confidence between 0 and 1 based on image legibility and field certainty."
    },
    rawText: { type: "string", description: "Best-effort OCR style plain text extracted from the receipt." },
    lineItems: {
      type: "array",
      description: "Individual line items when the receipt contains them.",
      items: {
        type: "object",
        properties: {
          name: { type: "string" },
          quantity: { type: "number" },
          unitPrice: { type: "number" },
          totalPrice: { type: "number" }
        }
      }
    }
  }
} as const;
