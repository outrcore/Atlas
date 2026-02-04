/**
 * Auto-RAG Context Injection
 *
 * Automatically searches memory/knowledge and injects relevant context
 * before the agent processes a message.
 */

import type { OpenClawConfig } from "../../../config/config.js";
import type { EmbeddedContextFile } from "../../pi-embedded-helpers.js";
import { resolveMemorySearchConfig } from "../../memory-search.js";
import { resolveAgentIdFromSessionKey } from "../../../routing/session-key.js";

export type AutoRagResult = {
  contextFile: EmbeddedContextFile | null;
  searchTimeMs: number;
  resultCount: number;
};

/**
 * Check if auto-RAG is enabled in config
 */
export function isAutoRagEnabled(cfg: OpenClawConfig | undefined, agentId: string): boolean {
  if (!cfg) return false;
  const memoryConfig = resolveMemorySearchConfig(cfg, agentId);
  if (!memoryConfig?.enabled) return false;

  // Check for autoInject at defaults level
  const defaultAutoInject = (cfg.agents?.defaults?.memorySearch as any)?.autoInject;
  return defaultAutoInject ?? false;
}

/**
 * Search memory and format results for context injection
 */
export async function searchAndInjectContext(params: {
  query: string;
  cfg: OpenClawConfig;
  agentId: string;
  sessionKey?: string;
  maxResults?: number;
  minScore?: number;
}): Promise<AutoRagResult> {
  const start = Date.now();

  try {
    // Dynamic import to avoid circular dependencies
    const { getMemorySearchManager } = await import("../../../memory/index.js");

    const { manager, error } = await getMemorySearchManager({
      cfg: params.cfg,
      agentId: params.agentId,
    });

    if (!manager || error) {
      return { contextFile: null, searchTimeMs: Date.now() - start, resultCount: 0 };
    }

    const results = await manager.search(params.query, {
      maxResults: params.maxResults ?? 5,
      minScore: params.minScore ?? 0.4,
      sessionKey: params.sessionKey,
    });

    if (results.length === 0) {
      return { contextFile: null, searchTimeMs: Date.now() - start, resultCount: 0 };
    }

    // Format results as markdown context
    const formattedContent = formatRagResults(results);

    const contextFile: EmbeddedContextFile = {
      path: "RETRIEVED_CONTEXT.md",
      content: formattedContent,
    };

    return {
      contextFile,
      searchTimeMs: Date.now() - start,
      resultCount: results.length,
    };
  } catch (err) {
    console.warn("[auto-rag] Search failed:", err instanceof Error ? err.message : String(err));
    return { contextFile: null, searchTimeMs: Date.now() - start, resultCount: 0 };
  }
}

/**
 * Format search results as markdown for injection
 */
function formatRagResults(
  results: Array<{ path: string; snippet: string; score: number }>,
): string {
  const lines = [
    "# Retrieved Context",
    "",
    "*The following context was automatically retrieved based on your query:*",
    "",
  ];

  for (const result of results) {
    const filename = result.path.split("/").pop() ?? result.path;
    lines.push(`## From: ${filename}`);
    lines.push("");
    lines.push(result.snippet.trim());
    lines.push("");
    lines.push("---");
    lines.push("");
  }

  return lines.join("\n");
}

/**
 * Main entry point for auto-RAG injection
 */
export async function maybeInjectRagContext(params: {
  userMessage: string;
  cfg: OpenClawConfig | undefined;
  sessionKey?: string;
  contextFiles: EmbeddedContextFile[];
}): Promise<{ contextFiles: EmbeddedContextFile[]; ragInjected: boolean }> {
  if (!params.cfg) {
    return { contextFiles: params.contextFiles, ragInjected: false };
  }

  const agentId = params.sessionKey ? resolveAgentIdFromSessionKey(params.sessionKey) : "main";

  if (!isAutoRagEnabled(params.cfg, agentId)) {
    return { contextFiles: params.contextFiles, ragInjected: false };
  }

  // Skip RAG for very short messages (commands, reactions, etc.)
  if (params.userMessage.length < 10 || params.userMessage.startsWith("/")) {
    return { contextFiles: params.contextFiles, ragInjected: false };
  }

  const result = await searchAndInjectContext({
    query: params.userMessage,
    cfg: params.cfg,
    agentId,
    sessionKey: params.sessionKey,
    maxResults: 5,
    minScore: 0.4,
  });

  if (!result.contextFile) {
    return { contextFiles: params.contextFiles, ragInjected: false };
  }

  // Inject at the beginning of context files
  return {
    contextFiles: [result.contextFile, ...params.contextFiles],
    ragInjected: true,
  };
}
