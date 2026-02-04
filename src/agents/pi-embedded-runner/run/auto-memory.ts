/**
 * Auto-Memory Extraction
 *
 * Automatically extracts memorable content from conversations
 * and writes to daily memory files after each response.
 *
 * Enhanced with:
 * - Conversation context (last N messages)
 * - Sonnet 4.5 for better extraction quality
 * - Deduplication against today's existing extractions
 */

import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import type { OpenClawConfig } from "../../../config/config.js";
import { resolveMemorySearchConfig } from "../../memory-search.js";
import { resolveAgentIdFromSessionKey } from "../../../routing/session-key.js";
import { resolveAgentWorkspaceDir } from "../../agent-scope.js";

export type MemoryExtraction = {
  facts: string[];
  decisions: string[];
  preferences: string[];
  actionItems: string[];
};

export type AutoMemoryResult = {
  extracted: boolean;
  written: boolean;
  extractionTimeMs: number;
  items: number;
  dedupedItems: number;
};

export type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
};

/**
 * Check if auto-memory extraction is enabled in config
 */
export function isAutoMemoryEnabled(cfg: OpenClawConfig | undefined, agentId: string): boolean {
  if (!cfg) return false;
  const memoryConfig = resolveMemorySearchConfig(cfg, agentId);
  if (!memoryConfig?.enabled) return false;

  const defaultAutoExtract = (cfg.agents?.defaults?.memorySearch as any)?.autoExtract;
  return defaultAutoExtract ?? false;
}

/**
 * Get API key from environment, config, or .env file
 */
function getAnthropicApiKey(cfg: OpenClawConfig): string | null {
  // Check environment variables
  const envKey = process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_OAUTH_TOKEN;
  if (envKey) return envKey;

  // Check config auth profiles
  const profiles = cfg.auth?.profiles;
  if (profiles) {
    for (const [key, profile] of Object.entries(profiles)) {
      if (key.startsWith("anthropic:") && (profile as any).token) {
        return (profile as any).token;
      }
    }
  }

  // Fallback: try to read from workspace .env file
  try {
    const workspaceDir = cfg.agents?.defaults?.workspace || "/workspace/clawd";
    const envPath = path.join(workspaceDir, ".env");
    const envContent = fsSync.readFileSync(envPath, "utf-8");
    const match = envContent.match(/ANTHROPIC_API_KEY=([^\n\r]+)/);
    if (match?.[1]) return match[1].trim();
  } catch {
    // Ignore errors reading .env
  }

  return null;
}

/**
 * Load today's existing extractions for deduplication
 */
async function loadTodaysExtractions(workspaceDir: string): Promise<string[]> {
  try {
    const memoryDir = path.join(workspaceDir, "memory");
    const dateStr = new Date().toISOString().split("T")[0];
    const filepath = path.join(memoryDir, `${dateStr}.md`);

    const content = await fs.readFile(filepath, "utf-8");

    // Extract all bullet points from Auto-extracted sections
    const existingItems: string[] = [];
    const lines = content.split("\n");
    let inAutoExtracted = false;

    for (const line of lines) {
      if (line.includes("Auto-extracted")) {
        inAutoExtracted = true;
        continue;
      }
      if (line.startsWith("###") || line.startsWith("> Context:")) {
        inAutoExtracted = false;
        continue;
      }
      if (inAutoExtracted && line.startsWith("- ")) {
        // Normalize and store the first 80 chars as fingerprint
        const item = line.slice(2).toLowerCase().trim().slice(0, 80);
        if (item.length > 10) {
          existingItems.push(item);
        }
      }
    }

    return existingItems;
  } catch {
    return [];
  }
}

/**
 * Check if an item is a duplicate of existing extractions
 */
function isDuplicate(item: string, existingItems: string[]): boolean {
  const normalized = item.toLowerCase().trim().slice(0, 80);
  for (const existing of existingItems) {
    // Check for exact match or high similarity (first 50 chars)
    if (normalized === existing || normalized.slice(0, 50) === existing.slice(0, 50)) {
      return true;
    }
  }
  return false;
}

/**
 * Deduplicate extraction against today's existing items
 */
function deduplicateExtraction(
  extraction: MemoryExtraction,
  existingItems: string[],
): { extraction: MemoryExtraction; removedCount: number } {
  let removedCount = 0;

  const dedupArray = (arr: string[]): string[] => {
    return arr.filter((item) => {
      if (isDuplicate(item, existingItems)) {
        removedCount++;
        return false;
      }
      return true;
    });
  };

  return {
    extraction: {
      facts: dedupArray(extraction.facts),
      decisions: dedupArray(extraction.decisions),
      preferences: dedupArray(extraction.preferences),
      actionItems: dedupArray(extraction.actionItems),
    },
    removedCount,
  };
}

/**
 * Extract memorable content using Claude Sonnet 4.5
 */
async function extractMemories(params: {
  userMessage: string;
  assistantResponse: string;
  cfg: OpenClawConfig;
  conversationContext?: ConversationMessage[];
}): Promise<MemoryExtraction | null> {
  try {
    const apiKey = getAnthropicApiKey(params.cfg);
    if (!apiKey) {
      console.warn("[auto-memory] No Anthropic API key found");
      return null;
    }

    // Build conversation context string
    let contextStr = "";
    if (params.conversationContext && params.conversationContext.length > 0) {
      contextStr = "## Recent Conversation Context:\n";
      for (const msg of params.conversationContext) {
        const role = msg.role === "user" ? "USER" : "ASSISTANT";
        const content = msg.content.slice(0, 300) + (msg.content.length > 300 ? "..." : "");
        contextStr += `${role}: ${content}\n\n`;
      }
      contextStr += "---\n\n";
    }

    const prompt = `Analyze this conversation and extract any information worth remembering long-term.

${contextStr}## Current Exchange:
USER: ${params.userMessage}

ASSISTANT: ${params.assistantResponse}

Extract ONLY genuinely memorable content:
- **Facts**: New information learned (about the user, projects, technical details, system configs)
- **Decisions**: Choices made about approach, tools, architecture, or direction
- **Preferences**: User preferences, likes/dislikes, working style, rules they've established
- **Action Items**: Tasks to do, follow-ups needed, things to remember

Be HIGHLY SELECTIVE:
- Skip routine work updates ("I'll check that", "Done")
- Skip simple acknowledgments and confirmations
- Skip technical implementation details unless they're key decisions
- Focus on what would be valuable to remember in FUTURE sessions

If nothing is genuinely memorable, return empty arrays.

Respond in JSON format ONLY (no explanation):
{
  "facts": ["fact 1", "fact 2"],
  "decisions": ["decision 1"],
  "preferences": ["preference 1"],
  "actionItems": ["todo 1"]
}`;

    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514", // Upgraded to Sonnet for better extraction
        max_tokens: 500,
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!response.ok) {
      console.warn("[auto-memory] API request failed:", response.status);
      return null;
    }

    const data = (await response.json()) as any;
    const text = data.content?.[0]?.text;
    if (!text) return null;

    // Parse JSON from response
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) return null;

    const extraction = JSON.parse(jsonMatch[0]) as MemoryExtraction;
    return extraction;
  } catch (err) {
    console.warn(
      "[auto-memory] Extraction failed:",
      err instanceof Error ? err.message : String(err),
    );
    return null;
  }
}

/**
 * Format extraction as markdown and append to daily memory file
 */
async function writeToMemory(params: {
  extraction: MemoryExtraction;
  workspaceDir: string;
  userMessage: string;
  assistantResponse: string;
}): Promise<boolean> {
  try {
    const memoryDir = path.join(params.workspaceDir, "memory");
    await fs.mkdir(memoryDir, { recursive: true });

    const now = new Date();
    const dateStr = now.toISOString().split("T")[0];
    const timeStr = now.toISOString().split("T")[1]?.split(".")[0];
    const filename = `${dateStr}.md`;
    const filepath = path.join(memoryDir, filename);

    const lines: string[] = [];
    lines.push("");
    lines.push(`### Auto-extracted (${timeStr} UTC)`);

    if (params.extraction.facts.length > 0) {
      lines.push("**Facts:**");
      params.extraction.facts.forEach((f) => lines.push(`- ${f}`));
    }

    if (params.extraction.decisions.length > 0) {
      lines.push("**Decisions:**");
      params.extraction.decisions.forEach((d) => lines.push(`- ${d}`));
    }

    if (params.extraction.preferences.length > 0) {
      lines.push("**Preferences:**");
      params.extraction.preferences.forEach((p) => lines.push(`- ${p}`));
    }

    if (params.extraction.actionItems.length > 0) {
      lines.push("**Action Items:**");
      params.extraction.actionItems.forEach((a) => lines.push(`- ${a}`));
    }

    // Show context from both sides of the conversation
    const userCtx = params.userMessage.slice(0, 80) + (params.userMessage.length > 80 ? "..." : "");
    const assistCtx =
      params.assistantResponse.slice(0, 80) + (params.assistantResponse.length > 80 ? "..." : "");
    lines.push(`> Context: "${userCtx}"`);
    lines.push("");

    const content = lines.join("\n");
    await fs.appendFile(filepath, content, "utf-8");

    return true;
  } catch (err) {
    console.warn("[auto-memory] Write failed:", err instanceof Error ? err.message : String(err));
    return false;
  }
}

/**
 * Count total items in extraction
 */
function countItems(extraction: MemoryExtraction): number {
  return (
    extraction.facts.length +
    extraction.decisions.length +
    extraction.preferences.length +
    extraction.actionItems.length
  );
}

/**
 * Main entry point for auto-memory extraction (runs async after response)
 */
export async function maybeExtractAndSaveMemory(params: {
  userMessage: string;
  assistantResponse: string;
  cfg: OpenClawConfig | undefined;
  sessionKey?: string;
  conversationContext?: ConversationMessage[];
}): Promise<AutoMemoryResult> {
  const start = Date.now();
  const defaultResult: AutoMemoryResult = {
    extracted: false,
    written: false,
    extractionTimeMs: 0,
    items: 0,
    dedupedItems: 0,
  };

  const debugLog = (msg: string) => {
    try {
      fsSync.appendFileSync("/tmp/auto-memory-debug.log", `[${new Date().toISOString()}] ${msg}\n`);
    } catch {}
  };

  if (!params.cfg) {
    debugLog("SKIP: no cfg");
    return { ...defaultResult, extractionTimeMs: Date.now() - start };
  }

  const agentId = params.sessionKey ? resolveAgentIdFromSessionKey(params.sessionKey) : "main";

  if (!isAutoMemoryEnabled(params.cfg, agentId)) {
    debugLog(`SKIP: autoMemory not enabled for agent ${agentId}`);
    return { ...defaultResult, extractionTimeMs: Date.now() - start };
  }

  debugLog(`Processing for agent ${agentId}`);

  // Skip very short messages or commands
  if (params.userMessage.length < 15 || params.userMessage.startsWith("/")) {
    debugLog(`SKIP: message too short (${params.userMessage.length}) or command`);
    return { ...defaultResult, extractionTimeMs: Date.now() - start };
  }

  // Skip if assistant response is too short (likely an error or simple ack)
  if (params.assistantResponse.length < 50) {
    debugLog(`SKIP: response too short (${params.assistantResponse.length})`);
    return { ...defaultResult, extractionTimeMs: Date.now() - start };
  }

  debugLog(
    `Proceeding with extraction... user=${params.userMessage.length}chars, assistant=${params.assistantResponse.length}chars`,
  );

  // Extract memories with conversation context
  const extraction = await extractMemories({
    userMessage: params.userMessage,
    assistantResponse: params.assistantResponse,
    cfg: params.cfg,
    conversationContext: params.conversationContext,
  });

  if (!extraction || countItems(extraction) === 0) {
    debugLog("SKIP: no items extracted");
    return { ...defaultResult, extracted: true, extractionTimeMs: Date.now() - start };
  }

  // Get workspace dir and load existing extractions for dedup
  const workspaceDir = resolveAgentWorkspaceDir(params.cfg, agentId);
  const existingItems = await loadTodaysExtractions(workspaceDir);

  // Deduplicate against today's existing extractions
  const { extraction: dedupedExtraction, removedCount } = deduplicateExtraction(
    extraction,
    existingItems,
  );

  if (removedCount > 0) {
    debugLog(`Deduped ${removedCount} items against today's extractions`);
  }

  // Check if anything remains after dedup
  if (countItems(dedupedExtraction) === 0) {
    debugLog("SKIP: all items were duplicates");
    return {
      ...defaultResult,
      extracted: true,
      extractionTimeMs: Date.now() - start,
      dedupedItems: removedCount,
    };
  }

  // Write to memory file
  const written = await writeToMemory({
    extraction: dedupedExtraction,
    workspaceDir,
    userMessage: params.userMessage,
    assistantResponse: params.assistantResponse,
  });

  return {
    extracted: true,
    written,
    extractionTimeMs: Date.now() - start,
    items: countItems(dedupedExtraction),
    dedupedItems: removedCount,
  };
}

/**
 * Fire-and-forget wrapper for async memory extraction
 * Call this after response completes - it won't block
 */
export function triggerMemoryExtraction(params: {
  userMessage: string;
  assistantResponse: string;
  cfg: OpenClawConfig | undefined;
  sessionKey?: string;
  conversationContext?: ConversationMessage[];
}): void {
  // Debug: write to file to confirm function is called
  try {
    fsSync.appendFileSync(
      "/tmp/auto-memory-debug.log",
      `[${new Date().toISOString()}] Triggered for: "${params.userMessage.slice(0, 50)}"\n`,
    );
  } catch {}

  console.log(`[auto-memory] Triggered for message: "${params.userMessage.slice(0, 50)}..."`);

  // Run async, don't await
  maybeExtractAndSaveMemory(params)
    .then((result) => {
      const dedupMsg = result.dedupedItems > 0 ? `, deduped=${result.dedupedItems}` : "";
      console.log(
        `[auto-memory] Result: extracted=${result.extracted}, written=${result.written}, items=${result.items}${dedupMsg}`,
      );
      if (result.written && result.items > 0) {
        console.log(
          `[auto-memory] Extracted ${result.items} items in ${result.extractionTimeMs}ms`,
        );
      }
    })
    .catch((err) => {
      console.warn("[auto-memory] Background extraction failed:", err);
    });
}
