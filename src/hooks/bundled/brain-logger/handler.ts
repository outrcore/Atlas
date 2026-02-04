/**
 * Brain Logger Hook - Logs all messages to ATLAS brain activity system
 *
 * Triggers on:
 * - agent:turn-end - When a turn completes (message received + response sent)
 * - command:new - When session resets
 */

import fs from "node:fs";
import path from "node:path";
import type { HookHandler } from "../../hooks.js";

const BRAIN_ACTIVITY_DIR = "/workspace/clawd/brain_data/activity";
const MEMORY_DIR = "/workspace/clawd/memory";

// Ensure directories exist
function ensureDirs() {
  if (!fs.existsSync(BRAIN_ACTIVITY_DIR)) {
    fs.mkdirSync(BRAIN_ACTIVITY_DIR, { recursive: true });
  }
  if (!fs.existsSync(MEMORY_DIR)) {
    fs.mkdirSync(MEMORY_DIR, { recursive: true });
  }
}

function getDateStr(): string {
  return new Date().toISOString().split("T")[0]!;
}

function getTimeStr(): string {
  return new Date().toISOString().split("T")[1]!.split(".")[0]!;
}

function logActivity(type: string, content: string, metadata: Record<string, unknown> = {}) {
  ensureDirs();
  const logFile = path.join(BRAIN_ACTIVITY_DIR, `${getDateStr()}.jsonl`);
  const entry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: new Date().toISOString(),
    type,
    content: content.substring(0, 1000), // Limit size
    metadata,
  };

  fs.appendFileSync(logFile, JSON.stringify(entry) + "\n");
}

function appendToDailyMemory(content: string) {
  ensureDirs();
  const memFile = path.join(MEMORY_DIR, `${getDateStr()}.md`);

  // Create file with header if it doesn't exist
  if (!fs.existsSync(memFile)) {
    fs.writeFileSync(memFile, `# ${getDateStr()} Daily Log\n\n`);
  }

  fs.appendFileSync(memFile, content + "\n");
}

const brainLoggerHook: HookHandler = async (event) => {
  try {
    const context = event.context || {};
    const channel = (context.channel as string) || "unknown";

    // Log based on event type
    if (event.type === "agent" && event.action === "turn-end") {
      // A turn completed - log the exchange
      const userMessage = context.userMessage as string | undefined;
      const assistantMessage = context.assistantMessage as string | undefined;

      if (userMessage) {
        logActivity("conversation", `[user] ${userMessage}`, {
          channel,
          sessionKey: event.sessionKey,
          role: "user",
        });

        // Also append to daily memory for main channels
        if (channel === "telegram" || channel === "discord") {
          appendToDailyMemory(
            `### ${channel} (${getTimeStr()} UTC)\n**User:** ${userMessage.substring(0, 500)}\n`,
          );
        }
      }

      if (assistantMessage) {
        logActivity("conversation", `[assistant] ${assistantMessage}`, {
          channel,
          sessionKey: event.sessionKey,
          role: "assistant",
        });

        if (channel === "telegram" || channel === "discord") {
          appendToDailyMemory(`**ATLAS:** ${assistantMessage.substring(0, 300)}...\n`);
        }
      }
    }

    // Log session events
    if (event.type === "command" && event.action === "new") {
      logActivity("session_new", `New session started: ${event.sessionKey}`, {
        channel,
        sessionKey: event.sessionKey,
      });
    }

    // Log gateway events
    if (event.type === "gateway") {
      logActivity("gateway", `Gateway ${event.action}`, {
        action: event.action,
      });
    }
  } catch (err) {
    console.error("[brain-logger] Error logging:", err);
  }
};

export default brainLoggerHook;
