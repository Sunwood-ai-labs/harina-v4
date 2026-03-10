import { Client, Events, GatewayIntentBits } from "discord.js";

import { appConfig } from "./config.js";
import { ensureReceiptSheet } from "./services/sheets.js";
import {
  buildSuccessReply,
  getReceiptAttachments,
  processReceiptAttachment
} from "./services/receipt-pipeline.js";

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent]
});

client.once(Events.ClientReady, async (readyClient) => {
  try {
    await ensureReceiptSheet(appConfig.googleSheetsSpreadsheetId, appConfig.googleSheetsSheetName);
    console.log(`Receipt bot is ready as ${readyClient.user.tag}`);
  } catch (error) {
    console.error("Startup initialization failed", error);
    readyClient.destroy();
    process.exit(1);
  }
});

client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) {
    return;
  }

  if (appConfig.allowedChannelIds.size > 0 && !appConfig.allowedChannelIds.has(message.channelId)) {
    return;
  }

  const receiptAttachments = getReceiptAttachments(message);

  if (receiptAttachments.size === 0) {
    return;
  }

  try {
    await message.react("🧾");

    const results = [];

    for (const attachment of receiptAttachments.values()) {
      const result = await processReceiptAttachment(message, attachment);
      results.push(result);
    }

    await message.reply({
      content: buildSuccessReply(results)
    });
  } catch (error) {
    console.error("Receipt processing failed", error);
    await message.reply({
      content:
        "レシートの処理に失敗しました。Gemini / Google Drive / Google Sheets の設定と画像形式を確認してください。"
    });
  }
});

client.login(appConfig.discordToken).catch((error) => {
  console.error("Discord login failed", error);
  process.exitCode = 1;
});
