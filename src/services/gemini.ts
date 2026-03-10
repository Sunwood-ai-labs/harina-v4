import { GoogleGenAI } from "@google/genai";

import { appConfig } from "../config.js";
import { receiptExtractionSchema, receiptResponseSchema, type ReceiptExtraction } from "../receipt-schema.js";

export type ReceiptImageInput = {
  data: Buffer;
  mimeType: string;
  fileName: string;
};

const ai = new GoogleGenAI({ apiKey: appConfig.geminiApiKey });

const receiptPrompt = [
  "You are extracting structured receipt data for bookkeeping automation.",
  "Read the receipt image and return only JSON that matches the requested schema.",
  "If a field is missing, omit it instead of inventing data.",
  "Use ISO 8601 date format when the date is clear.",
  "Numbers must be plain numbers without currency symbols or commas.",
  "Include lineItems when they can be read confidently.",
  "Set confidence to a value between 0 and 1."
].join(" ");

export async function extractReceiptData(input: ReceiptImageInput): Promise<ReceiptExtraction> {
  const response = await ai.models.generateContent({
    model: appConfig.geminiModel,
    contents: [
      {
        inlineData: {
          mimeType: input.mimeType,
          data: input.data.toString("base64")
        }
      },
      {
        text: `${receiptPrompt}\nReceipt file name: ${input.fileName}`
      }
    ],
    config: {
      temperature: 0.1,
      responseMimeType: "application/json",
      responseSchema: receiptResponseSchema
    }
  });

  const jsonText = response.text?.trim();

  if (!jsonText) {
    throw new Error("Gemini returned an empty response.");
  }

  const parsed = JSON.parse(jsonText);
  return receiptExtractionSchema.parse(parsed);
}
