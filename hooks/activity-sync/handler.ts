/**
 * Activity Sync Hook
 * 
 * Updates .activity.json for cross-platform context sharing.
 * Allows Discord-ATLAS to see what Telegram-ATLAS is doing.
 */

import fs from "node:fs/promises";

const ACTIVITY_FILE = "/workspace/clawd/.activity.json";

interface ActivityData {
  current: string;
  channel: string;
  sessionKey?: string;
  action?: string;
  updated: string;
}

interface HookEvent {
  type: string;
  action: string;
  sessionKey: string;
  context: Record<string, unknown>;
  timestamp: Date;
  messages: string[];
}

async function updateActivity(data: Partial<ActivityData>): Promise<void> {
  const activity: ActivityData = {
    current: data.current || "Processing...",
    channel: data.channel || "telegram",
    sessionKey: data.sessionKey,
    action: data.action,
    updated: new Date().toISOString(),
  };

  try {
    await fs.writeFile(ACTIVITY_FILE, JSON.stringify(activity, null, 2), "utf-8");
  } catch (err) {
    console.error("[activity-sync] Failed to write activity:", err);
  }
}

/**
 * Main hook handler - updates activity file on each event
 */
const activitySyncHandler = async (event: HookEvent): Promise<void> => {
  const { type, action, sessionKey, context } = event;

  // Determine channel from context
  const channel = (context.messageChannel as string) || 
                  (context.channel as string) || 
                  "telegram";

  // Build activity description based on event
  let current = "Processing...";

  if (type === "command") {
    switch (action) {
      case "new":
        current = "Starting new conversation";
        break;
      case "reset":
        current = "Resetting conversation";
        break;
      case "stop":
        current = "Stopping current task";
        break;
      case "status":
        current = "Checking status";
        break;
      default:
        current = `Running /${action}`;
    }
  } else if (type === "agent") {
    if (action === "bootstrap") {
      current = "Initializing session";
    } else {
      current = `Agent: ${action}`;
    }
  } else if (type === "session") {
    current = `Session: ${action}`;
  } else if (type === "gateway") {
    if (action === "startup") {
      current = "Gateway starting up";
    } else {
      current = `Gateway: ${action}`;
    }
  }

  // Include sender info if available
  const senderName = context.senderName as string | undefined;
  const senderId = context.senderId as string | undefined;
  
  if (senderName) {
    current = `${current} (with ${senderName})`;
  } else if (senderId) {
    current = `${current} (user ${senderId})`;
  }

  await updateActivity({
    current,
    channel,
    sessionKey,
    action,
  });
};

export default activitySyncHandler;
