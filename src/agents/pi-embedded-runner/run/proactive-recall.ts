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

import fsSync from "node:fs";
import fs from "node:fs/promises";
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
  contextType: "semantic" | "keyword" | "entity" | "temporal" | "knowledge";
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
 * Knowledge library search (Dewey Decimal system)
 * Searches knowledge folder recursively for .md files
 */
let knowledgeCache: { files: { path: string; content: string }[]; loadedAt: number } | null = null;
const KNOWLEDGE_CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

async function loadKnowledgeFiles(workspaceDir: string): Promise<{ path: string; content: string }[]> {
  const now = Date.now();

  if (knowledgeCache && now - knowledgeCache.loadedAt < KNOWLEDGE_CACHE_TTL_MS) {
    return knowledgeCache.files;
  }

  const knowledgeDir = path.join(workspaceDir, "knowledge");
  const files: { path: string; content: string }[] = [];

  try {
    // Recursively find all .md files
    const walkDir = async (dir: string): Promise<void> => {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          await walkDir(fullPath);
        } else if (entry.name.endsWith(".md")) {
          try {
            const content = await fs.readFile(fullPath, "utf-8");
            const relativePath = path.relative(workspaceDir, fullPath);
            files.push({ path: relativePath, content });
          } catch {
            // Skip unreadable files
          }
        }
      }
    };

    await walkDir(knowledgeDir);
    knowledgeCache = { files, loadedAt: now };
  } catch {
    // Knowledge dir doesn't exist
  }

  return files;
}

async function knowledgeSearch(
  query: string,
  workspaceDir: string,
  limit: number = 3,
): Promise<RecallResult[]> {
  const results: RecallResult[] = [];
  const files = await loadKnowledgeFiles(workspaceDir);

  const queryWords = new Set(
    query
      .toLowerCase()
      .split(/\s+/)
      .filter((w) => w.length > 2),
  );

  if (queryWords.size === 0) return results;

  for (const file of files) {
    const contentLower = file.content.toLowerCase();

    // Count matching words
    let matches = 0;
    for (const word of queryWords) {
      if (contentLower.includes(word)) matches++;
    }

    if (matches > 0) {
      const relevance = matches / queryWords.size;

      // Find the most relevant chunk
      const chunks = file.content.split(/\n\n+/);
      let bestChunk = "";
      let bestScore = 0;

      for (const chunk of chunks) {
        const chunkLower = chunk.toLowerCase();
        let chunkMatches = 0;
        for (const word of queryWords) {
          if (chunkLower.includes(word)) chunkMatches++;
        }
        if (chunkMatches > bestScore) {
          bestScore = chunkMatches;
          bestChunk = chunk.trim().slice(0, 400);
        }
      }

      if (bestChunk) {
        results.push({
          content: bestChunk,
          source: file.path,
          relevanceScore: relevance,
          contextType: "knowledge",
          category: file.path.split("/")[1], // e.g., "100-projects"
        });
      }
    }
  }

  // Sort by relevance and return top N
  results.sort((a, b) => b.relevanceScore - a.relevanceScore);
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

// ─────────────────────────────────────────────────────────────
// Tier 1: Fast entity cache (avoids HTTP call for simple messages)
// ─────────────────────────────────────────────────────────────
let entityCache: { names: Set<string>; loadedAt: number } | null = null;
const ENTITY_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
const UMA_BRIDGE_URL = "http://127.0.0.1:18790";

// Memory-related keywords that should always trigger full search
const MEMORY_KEYWORDS = new Set([
  "remember",
  "recall",
  "what did",
  "when did",
  "last time",
  "decided",
  "decision",
  "tell me about",
  "history",
  "previously",
  "before",
  "earlier",
  "yesterday",
  "last week",
  "remind",
]);

async function loadEntityCache(): Promise<Set<string>> {
  const now = Date.now();
  if (entityCache && now - entityCache.loadedAt < ENTITY_CACHE_TTL_MS) {
    return entityCache.names;
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000); // 3s for entity cache
    const resp = await fetch(`${UMA_BRIDGE_URL}/entities`, { signal: controller.signal });
    clearTimeout(timeout);

    if (resp.ok) {
      const data = (await resp.json()) as { entities?: string[] };
      const names = new Set(data.entities ?? []);
      entityCache = { names, loadedAt: now };
      return names;
    }
  } catch {
    // Bridge not running
  }
  return entityCache?.names ?? new Set();
}

/**
 * Tier 1: Quick check if a message references any known entities or memory keywords.
 * Returns true if full UMA search should run. ~1ms, no HTTP call after cache warm.
 */
async function shouldRunFullUmaSearch(query: string): Promise<boolean> {
  const queryLower = query.toLowerCase();

  // Check memory keywords first (cheap string check)
  for (const keyword of MEMORY_KEYWORDS) {
    if (queryLower.includes(keyword)) return true;
  }

  // Check if query mentions any known entities
  const entities = await loadEntityCache();
  if (entities.size === 0) return true; // Cache empty, run full search to be safe

  for (const entity of entities) {
    if (entity.length > 2 && queryLower.includes(entity)) return true;
  }

  return false;
}

/**
 * Try UMA (Unified Memory Architecture) graph-enhanced search.
 * Falls back gracefully if the bridge isn't running.
 */
interface UmaSearchResult {
  results: RecallResult[];
  confidence: number;
  entities: string[];
  sources: string[];
}

async function tryUmaSearchFull(query: string, limit: number = 5): Promise<UmaSearchResult> {
  const empty: UmaSearchResult = { results: [], confidence: 0, entities: [], sources: [] };

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000); // 5s timeout (cold start can be slow)

    const url = `${UMA_BRIDGE_URL}/search?q=${encodeURIComponent(query)}&limit=${limit}`;
    console.log(`[proactive-recall] UMA calling: ${url}`);
    const resp = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (!resp.ok) {
      console.log(`[proactive-recall] UMA bridge returned ${resp.status}`);
      return empty;
    }

    const data = (await resp.json()) as {
      memories?: { content: string; source: string; score: number }[];
      graph_context?: { relationships?: { from: string; relation: string; to: string }[] };
      entities?: string[];
      confidence?: number;
      elapsed_ms?: number;
    };

    const results: RecallResult[] = [];
    const sources: string[] = [];

    // Convert UMA memories to RecallResults
    if (data.memories) {
      for (const mem of data.memories) {
        results.push({
          content: mem.content,
          source: mem.source || "graph",
          relevanceScore: mem.score,
          contextType: "entity",
        });
        if (mem.source && mem.source !== "graph") {
          sources.push(mem.source);
        }
      }
    }

    // Add graph relationships as context
    if (data.graph_context?.relationships) {
      for (const rel of data.graph_context.relationships.slice(0, 3)) {
        const content = `${rel.from} → ${rel.relation} → ${rel.to}`;
        results.push({
          content,
          source: "entity-graph",
          relevanceScore: 0.7,
          contextType: "entity",
        });
      }
    }

    if (results.length > 0) {
      console.log(
        `[proactive-recall] UMA returned ${results.length} results (${data.confidence?.toFixed(2)} confidence, ${data.elapsed_ms?.toFixed(0)}ms)`,
      );
      // Log top 3 results for debugging
      for (const r of results.slice(0, 3)) {
        const snippet = r.content.replace(/\n/g, " ").slice(0, 80);
        console.log(`[proactive-recall]   → [${r.relevanceScore.toFixed(3)}] ${snippet}...  (${r.source})`);
      }
    }

    return {
      results,
      confidence: data.confidence ?? 0,
      entities: data.entities ?? [],
      sources: [...new Set(sources)],
    };
  } catch (err) {
    console.log(`[proactive-recall] UMA search failed: ${err instanceof Error ? err.message : String(err)}`);
    return empty;
  }
}

/**
 * Tier 3: Agentic drill-down - read source files when confidence is low.
 * Calls the bridge's /drilldown endpoint which greps actual files.
 */
async function tryDrilldown(query: string, sources: string[], entities: string[]): Promise<RecallResult[]> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000); // 3s timeout (file I/O)

    const params = new URLSearchParams({
      q: query,
      sources: sources.slice(0, 5).join(","),
      entities: entities.slice(0, 3).join(","),
    });
    const url = `${UMA_BRIDGE_URL}/drilldown?${params}`;
    const resp = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (!resp.ok) return [];

    const data = (await resp.json()) as {
      snippets?: { text: string; source: string; line: number }[];
      count?: number;
      elapsed_ms?: number;
    };

    const results: RecallResult[] = [];

    if (data.snippets) {
      for (const snippet of data.snippets) {
        results.push({
          content: snippet.text,
          source: `${snippet.source}:${snippet.line}`,
          relevanceScore: 0.8, // Drill-down results are high quality
          contextType: "semantic",
        });
      }
    }

    if (results.length > 0 && data.elapsed_ms) {
      console.log(`[proactive-recall] Tier 3 drill-down: ${results.length} snippets in ${data.elapsed_ms.toFixed(0)}ms`);
    }

    return results;
  } catch {
    return [];
  }
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
  let umaConfidence = 0;
  let umaEntities: string[] = [];
  let umaSources: string[] = [];

  // 0. Tier 1: Quick entity check (~1ms) - skip full UMA for simple messages
  const needsUma = await shouldRunFullUmaSearch(query);
  if (needsUma) {
    // Tier 2: Full UMA graph-enhanced search (non-blocking, 2s timeout)
    const { results: umaResults, confidence: umConf, entities: umEnts, sources: umSrcs } = await tryUmaSearchFull(query, maxResults);
    allResults.push(...umaResults);
    umaConfidence = umConf;
    umaEntities = umEnts;
    umaSources = umSrcs;
    if (umaResults.length > 0) {
      console.log(`[proactive-recall] Tier 2: UMA returned ${umaResults.length} results (confidence: ${umConf.toFixed(2)})`);
    }
  } else {
    console.log(`[proactive-recall] Tier 1: No entities/keywords detected in query, skipping UMA`);
  }

  // 1. Load MEMORY.md and do keyword search
  const memoryContent = await getMemoryContent(workspaceDir);
  const keywordResults = keywordSearch(query, memoryContent, 3);
  allResults.push(...keywordResults);

  // 2. Entity search
  if (includeEntity) {
    const entityResults = entitySearch(query, memoryContent, 2);
    allResults.push(...entityResults);
  }

  // 3. Knowledge library search
  const knowledgeResults = await knowledgeSearch(query, workspaceDir, 2);
  allResults.push(...knowledgeResults);

  // 4. Temporal search (recent logs)
  if (includeTemporal) {
    const temporalResults = await temporalSearch(workspaceDir, 2);
    allResults.push(...temporalResults);
  }

  // Deduplicate and limit
  let uniqueResults = deduplicateResults(allResults).slice(0, maxResults);

  // Calculate confidence
  let confidence =
    uniqueResults.length > 0
      ? uniqueResults.reduce((sum, r) => sum + r.relevanceScore, 0) / uniqueResults.length
      : 0;

  // Tier 3: Agentic drill-down when confidence is low
  if (confidence < 0.7 && needsUma && (umaEntities.length > 0 || umaSources.length > 0)) {
    const drilldownResults = await tryDrilldown(query, umaSources, umaEntities);
    if (drilldownResults.length > 0) {
      console.log(`[proactive-recall] Tier 3: Drill-down found ${drilldownResults.length} snippets`);
      allResults.push(...drilldownResults);
      uniqueResults = deduplicateResults(allResults).slice(0, maxResults);
      confidence =
        uniqueResults.length > 0
          ? uniqueResults.reduce((sum, r) => sum + r.relevanceScore, 0) / uniqueResults.length
          : 0;
    }
  }

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
/**
 * Strip channel metadata from message to get clean query text.
 * Raw prompts look like: "[Telegram Matt (@MythicalSoup) id:476807845 ...] actual message\n[message_id: 4765]"
 */
function stripMessageMetadata(raw: string): string {
  let cleaned = raw;
  // Remove leading [Telegram/Discord/Signal ...] header
  cleaned = cleaned.replace(/^\[(?:Telegram|Discord|Signal|WhatsApp|Slack|iMessage)[^\]]*\]\s*/i, "");
  // Remove trailing [message_id: ...] 
  cleaned = cleaned.replace(/\s*\[message_id:\s*\d+\]\s*$/i, "");
  // Remove [Replying to ...] blocks
  cleaned = cleaned.replace(/\[Replying to[^\]]*\][\s\S]*?\[\/Replying\]\s*/gi, "");
  // Remove [media attached: ...] blocks
  cleaned = cleaned.replace(/\[media attached:[^\]]*\]\s*/gi, "");
  return cleaned.trim();
}

export async function getProactiveContext(params: {
  query: string;
  cfg: OpenClawConfig | undefined;
  sessionKey?: string;
  minConfidence?: number;
}): Promise<string | null> {
  const { query: rawQuery, cfg, sessionKey, minConfidence = 0.3 } = params;

  if (!cfg) return null;

  // Strip channel metadata for cleaner search
  const fullQuery = stripMessageMetadata(rawQuery);
  
  // For UMA search: extract the conversational part, skip logs/code dumps
  let query = fullQuery;
  if (query.length > 500) {
    // Check if it looks like pasted logs/code (lots of timestamps, brackets, technical patterns)
    const logIndicators = (query.match(/\d{2}:\d{2}:\d{2}|\[proactive-recall\]|\[auto-memory\]|\[telegram\]/g) || []).length;
    if (logIndicators > 3) {
      // Message is mostly logs — extract just the human's actual text before/after the paste
      const lines = query.split("\n");
      const humanLines = lines.filter(l => 
        !l.match(/^\d{2}:\d{2}/) && 
        !l.match(/^\s*\[/) && 
        l.trim().length > 10
      );
      query = humanLines.join(" ").slice(0, 500);
    } else {
      query = query.slice(0, 500);
    }
  }

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
      // Log final injected context sources
      const sources = context.recalledMemories.map(r => `${r.contextType}:${r.source}`);
      console.log(`[proactive-recall] Injecting from: ${[...new Set(sources)].join(", ")}`);
      return context.suggestedContext;
    } else {
      console.log(
        `[proactive-recall] Below threshold (${context.confidence.toFixed(2)} < ${minConfidence}) or no results. ${context.recalledMemories.length} candidates.`,
      );
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
