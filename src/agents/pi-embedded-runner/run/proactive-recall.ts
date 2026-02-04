/**
 * Proactive Recall - Enhanced Context Injection
 *
 * Searches multiple memory sources before responding and injects
 * relevant context. Enhances the basic auto-inject/RAG system.
 *
 * Search strategies:
 * 1. Semantic search (vector DB via Python bridge)
 * 2. Keyword search (MEMORY.md)
 * 3. Entity search (names, projects, technical terms)
 * 4. Temporal search (recent daily logs)
 */

import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import type { OpenClawConfig } from "../../../config/config.js";
import { resolveAgentIdFromSessionKey } from "../../../routing/session-key.js";
import { resolveAgentWorkspaceDir } from "../../agent-scope.js";

export interface RecallResult {
  content: string;
  source: string;
  relevanceScore: number;
  timestamp?: string;
  category?: string;
  contextType: "semantic" | "keyword" | "entity" | "temporal";
}

export interface ProactiveContext {
  query: string;
  recalledMemories: RecallResult[];
  suggestedContext: string;
  confidence: number;
  recallType: string;
  searchTimeMs: number;
}

/**
 * Load and cache MEMORY.md content
 */
let memoryCache: { content: string; loadedAt: number } | null = null;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

async function getMemoryContent(workspaceDir: string): Promise<string> {
  const now = Date.now();

  if (memoryCache && now - memoryCache.loadedAt < CACHE_TTL_MS) {
    return memoryCache.content;
  }

  const memoryPath = path.join(workspaceDir, "MEMORY.md");

  try {
    const content = await fs.readFile(memoryPath, "utf-8");
    memoryCache = { content, loadedAt: now };
    return content;
  } catch {
    return "";
  }
}

/**
 * Load recent daily logs
 */
async function getRecentDailyLogs(
  workspaceDir: string,
  days: number = 2,
): Promise<{ date: string; content: string }[]> {
  const logs: { date: string; content: string }[] = [];
  const memoryDir = path.join(workspaceDir, "memory");

  const now = new Date();

  for (let i = 0; i < days; i++) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split("T")[0];
    const logPath = path.join(memoryDir, `${dateStr}.md`);

    try {
      const content = await fs.readFile(logPath, "utf-8");
      logs.push({ date: dateStr!, content });
    } catch {
      // File doesn't exist, skip
    }
  }

  return logs;
}

/**
 * Keyword-based search in memory content
 */
function keywordSearch(query: string, content: string, limit: number = 5): RecallResult[] {
  const results: RecallResult[] = [];
  const queryWords = new Set(
    query
      .toLowerCase()
      .split(/\s+/)
      .filter((w) => w.length > 2),
  );

  if (queryWords.size === 0) return results;

  // Split content into chunks (paragraphs or list items)
  const chunks = content.split(/\n\n+/);

  for (const chunk of chunks) {
    const trimmed = chunk.trim();
    if (!trimmed || trimmed.length < 20) continue;

    const chunkLower = trimmed.toLowerCase();

    // Count matching words
    let matches = 0;
    for (const word of queryWords) {
      if (chunkLower.includes(word)) matches++;
    }

    if (matches > 0) {
      const relevance = matches / queryWords.size;
      results.push({
        content: trimmed.slice(0, 500),
        source: "MEMORY.md",
        relevanceScore: relevance,
        contextType: "keyword",
      });
    }
  }

  // Sort by relevance and return top N
  results.sort((a, b) => b.relevanceScore - a.relevanceScore);
  return results.slice(0, limit);
}

/**
 * Entity-based search (names, projects, technical terms)
 */
function entitySearch(query: string, content: string, limit: number = 5): RecallResult[] {
  const results: RecallResult[] = [];

  // Extract potential entities from query
  const entities: string[] = [];

  // Capitalized words (names, projects)
  const capitalizedMatches = query.match(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/g);
  if (capitalizedMatches) entities.push(...capitalizedMatches);

  // Quoted strings
  const quotedMatches = query.match(/["']([^"']+)["']/g);
  if (quotedMatches) {
    entities.push(...quotedMatches.map((m) => m.slice(1, -1)));
  }

  // Technical terms
  const techTerms = query
    .toLowerCase()
    .match(/\b(?:api|key|token|password|project|app|repo|server|database|config)\b/g);
  if (techTerms) entities.push(...techTerms);

  if (entities.length === 0) return results;

  // Search for each entity
  const lines = content.split("\n");
  const seenLines = new Set<string>();

  for (const entity of entities.slice(0, 5)) {
    const entityLower = entity.toLowerCase();

    for (const line of lines) {
      if (line.toLowerCase().includes(entityLower) && !seenLines.has(line)) {
        seenLines.add(line);
        results.push({
          content: line.trim().slice(0, 500),
          source: "MEMORY.md",
          relevanceScore: 0.8,
          contextType: "entity",
        });
        break; // One result per entity
      }
    }
  }

  return results.slice(0, limit);
}

/**
 * Temporal search (recent daily logs)
 */
async function temporalSearch(workspaceDir: string, limit: number = 3): Promise<RecallResult[]> {
  const results: RecallResult[] = [];
  const logs = await getRecentDailyLogs(workspaceDir, 2);

  for (let i = 0; i < logs.length; i++) {
    const log = logs[i];
    if (!log) continue;

    // Extract key sections (headers and important lines)
    const lines = log.content.split("\n");
    const keyLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("#") || line.startsWith("- **") || line.includes("Auto-extracted")) {
        keyLines.push(line);
      }
    }

    if (keyLines.length > 0) {
      results.push({
        content: keyLines.slice(0, 10).join("\n"),
        source: `memory/${log.date}.md`,
        relevanceScore: 0.7 - i * 0.2, // More recent = higher score
        timestamp: log.date,
        contextType: "temporal",
      });
    }
  }

  return results.slice(0, limit);
}

/**
 * Build context string from recall results
 */
function buildContextString(results: RecallResult[]): string {
  if (results.length === 0) return "";

  const parts = ["[Relevant context from memory:]"];

  for (const result of results) {
    let content = result.content.trim();
    if (content.length > 200) {
      content = content.slice(0, 200) + "...";
    }

    const sourceTag = result.source ? ` (${result.source})` : "";
    parts.push(`- ${content}${sourceTag}`);
  }

  return parts.join("\n");
}

/**
 * Deduplicate results by content
 */
function deduplicateResults(results: RecallResult[]): RecallResult[] {
  const seen = new Set<string>();
  const unique: RecallResult[] = [];

  // Sort by relevance first
  const sorted = [...results].sort((a, b) => b.relevanceScore - a.relevanceScore);

  for (const result of sorted) {
    const key = result.content.slice(0, 100).toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(result);
    }
  }

  return unique;
}

/**
 * Main proactive recall function
 */
export async function proactiveRecall(params: {
  query: string;
  workspaceDir: string;
  includeTemporal?: boolean;
  includeEntity?: boolean;
  maxResults?: number;
}): Promise<ProactiveContext> {
  const start = Date.now();
  const {
    query,
    workspaceDir,
    includeTemporal = true,
    includeEntity = true,
    maxResults = 5,
  } = params;

  const allResults: RecallResult[] = [];

  // 1. Load MEMORY.md and do keyword search
  const memoryContent = await getMemoryContent(workspaceDir);
  const keywordResults = keywordSearch(query, memoryContent, 3);
  allResults.push(...keywordResults);

  // 2. Entity search
  if (includeEntity) {
    const entityResults = entitySearch(query, memoryContent, 2);
    allResults.push(...entityResults);
  }

  // 3. Temporal search (recent logs)
  if (includeTemporal) {
    const temporalResults = await temporalSearch(workspaceDir, 2);
    allResults.push(...temporalResults);
  }

  // Deduplicate and limit
  const uniqueResults = deduplicateResults(allResults).slice(0, maxResults);

  // Calculate confidence
  const confidence =
    uniqueResults.length > 0
      ? uniqueResults.reduce((sum, r) => sum + r.relevanceScore, 0) / uniqueResults.length
      : 0;

  // Determine recall type
  let recallType = "none";
  if (uniqueResults.length > 0) {
    recallType = uniqueResults[0]!.contextType;
  }

  // Build context string
  const suggestedContext = buildContextString(uniqueResults);

  return {
    query,
    recalledMemories: uniqueResults,
    suggestedContext,
    confidence,
    recallType,
    searchTimeMs: Date.now() - start,
  };
}

/**
 * Get context injection for a query (convenience function)
 * Returns null if no relevant context found
 */
export async function getProactiveContext(params: {
  query: string;
  cfg: OpenClawConfig | undefined;
  sessionKey?: string;
  minConfidence?: number;
}): Promise<string | null> {
  const { query, cfg, sessionKey, minConfidence = 0.3 } = params;

  if (!cfg) return null;

  // Skip very short queries
  if (query.length < 10) return null;

  const agentId = sessionKey ? resolveAgentIdFromSessionKey(sessionKey) : "main";

  const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);

  try {
    const context = await proactiveRecall({
      query,
      workspaceDir,
    });

    if (context.confidence >= minConfidence && context.recalledMemories.length > 0) {
      console.log(
        `[proactive-recall] Found ${context.recalledMemories.length} memories (${context.confidence.toFixed(2)} confidence) in ${context.searchTimeMs}ms`,
      );
      return context.suggestedContext;
    }
  } catch (err) {
    console.warn("[proactive-recall] Error:", err instanceof Error ? err.message : String(err));
  }

  return null;
}

/**
 * Check if proactive recall should run for this message
 */
export function shouldRunProactiveRecall(query: string): boolean {
  // Skip commands
  if (query.startsWith("/")) return false;

  // Skip very short messages
  if (query.length < 15) return false;

  // Skip system messages
  if (query.startsWith("System:")) return false;

  return true;
}
