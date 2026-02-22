import { t as __exportAll } from "./rolldown-runtime-Cbj13DAv.js";
import { s as resolveAgentWorkspaceDir } from "./agent-scope-Csu2B6AM.js";
import { N as resolveUserPath, l as createSubsystemLogger } from "./exec-BMnoMcZW.js";
import { t as parseDurationMs } from "./parse-duration-CMajTpz1.js";
import path from "node:path";

//#region src/utils/shell-argv.ts
function splitShellArgs(raw) {
	const tokens = [];
	let buf = "";
	let inSingle = false;
	let inDouble = false;
	let escaped = false;
	const pushToken = () => {
		if (buf.length > 0) {
			tokens.push(buf);
			buf = "";
		}
	};
	for (let i = 0; i < raw.length; i += 1) {
		const ch = raw[i];
		if (escaped) {
			buf += ch;
			escaped = false;
			continue;
		}
		if (!inSingle && !inDouble && ch === "\\") {
			escaped = true;
			continue;
		}
		if (inSingle) {
			if (ch === "'") inSingle = false;
			else buf += ch;
			continue;
		}
		if (inDouble) {
			if (ch === "\"") inDouble = false;
			else buf += ch;
			continue;
		}
		if (ch === "'") {
			inSingle = true;
			continue;
		}
		if (ch === "\"") {
			inDouble = true;
			continue;
		}
		if (/\s/.test(ch)) {
			pushToken();
			continue;
		}
		buf += ch;
	}
	if (escaped || inSingle || inDouble) return null;
	pushToken();
	return tokens;
}

//#endregion
//#region src/memory/backend-config.ts
const DEFAULT_BACKEND = "builtin";
const DEFAULT_CITATIONS = "auto";
const DEFAULT_QMD_INTERVAL = "5m";
const DEFAULT_QMD_DEBOUNCE_MS = 15e3;
const DEFAULT_QMD_TIMEOUT_MS = 4e3;
const DEFAULT_QMD_EMBED_INTERVAL = "60m";
const DEFAULT_QMD_LIMITS = {
	maxResults: 6,
	maxSnippetChars: 700,
	maxInjectedChars: 4e3,
	timeoutMs: DEFAULT_QMD_TIMEOUT_MS
};
const DEFAULT_QMD_SCOPE = {
	default: "deny",
	rules: [{
		action: "allow",
		match: { chatType: "direct" }
	}]
};
function sanitizeName(input) {
	return input.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "") || "collection";
}
function ensureUniqueName(base, existing) {
	let name = sanitizeName(base);
	if (!existing.has(name)) {
		existing.add(name);
		return name;
	}
	let suffix = 2;
	while (existing.has(`${name}-${suffix}`)) suffix += 1;
	const unique = `${name}-${suffix}`;
	existing.add(unique);
	return unique;
}
function resolvePath(raw, workspaceDir) {
	const trimmed = raw.trim();
	if (!trimmed) throw new Error("path required");
	if (trimmed.startsWith("~") || path.isAbsolute(trimmed)) return path.normalize(resolveUserPath(trimmed));
	return path.normalize(path.resolve(workspaceDir, trimmed));
}
function resolveIntervalMs(raw) {
	const value = raw?.trim();
	if (!value) return parseDurationMs(DEFAULT_QMD_INTERVAL, { defaultUnit: "m" });
	try {
		return parseDurationMs(value, { defaultUnit: "m" });
	} catch {
		return parseDurationMs(DEFAULT_QMD_INTERVAL, { defaultUnit: "m" });
	}
}
function resolveEmbedIntervalMs(raw) {
	const value = raw?.trim();
	if (!value) return parseDurationMs(DEFAULT_QMD_EMBED_INTERVAL, { defaultUnit: "m" });
	try {
		return parseDurationMs(value, { defaultUnit: "m" });
	} catch {
		return parseDurationMs(DEFAULT_QMD_EMBED_INTERVAL, { defaultUnit: "m" });
	}
}
function resolveDebounceMs(raw) {
	if (typeof raw === "number" && Number.isFinite(raw) && raw >= 0) return Math.floor(raw);
	return DEFAULT_QMD_DEBOUNCE_MS;
}
function resolveLimits(raw) {
	const parsed = { ...DEFAULT_QMD_LIMITS };
	if (raw?.maxResults && raw.maxResults > 0) parsed.maxResults = Math.floor(raw.maxResults);
	if (raw?.maxSnippetChars && raw.maxSnippetChars > 0) parsed.maxSnippetChars = Math.floor(raw.maxSnippetChars);
	if (raw?.maxInjectedChars && raw.maxInjectedChars > 0) parsed.maxInjectedChars = Math.floor(raw.maxInjectedChars);
	if (raw?.timeoutMs && raw.timeoutMs > 0) parsed.timeoutMs = Math.floor(raw.timeoutMs);
	return parsed;
}
function resolveSessionConfig(cfg, workspaceDir) {
	const enabled = Boolean(cfg?.enabled);
	const exportDirRaw = cfg?.exportDir?.trim();
	return {
		enabled,
		exportDir: exportDirRaw ? resolvePath(exportDirRaw, workspaceDir) : void 0,
		retentionDays: cfg?.retentionDays && cfg.retentionDays > 0 ? Math.floor(cfg.retentionDays) : void 0
	};
}
function resolveCustomPaths(rawPaths, workspaceDir, existing) {
	if (!rawPaths?.length) return [];
	const collections = [];
	rawPaths.forEach((entry, index) => {
		const trimmedPath = entry?.path?.trim();
		if (!trimmedPath) return;
		let resolved;
		try {
			resolved = resolvePath(trimmedPath, workspaceDir);
		} catch {
			return;
		}
		const pattern = entry.pattern?.trim() || "**/*.md";
		const name = ensureUniqueName(entry.name?.trim() || `custom-${index + 1}`, existing);
		collections.push({
			name,
			path: resolved,
			pattern,
			kind: "custom"
		});
	});
	return collections;
}
function resolveDefaultCollections(include, workspaceDir, existing) {
	if (!include) return [];
	return [
		{
			path: workspaceDir,
			pattern: "MEMORY.md",
			base: "memory-root"
		},
		{
			path: workspaceDir,
			pattern: "memory.md",
			base: "memory-alt"
		},
		{
			path: path.join(workspaceDir, "memory"),
			pattern: "**/*.md",
			base: "memory-dir"
		}
	].map((entry) => ({
		name: ensureUniqueName(entry.base, existing),
		path: entry.path,
		pattern: entry.pattern,
		kind: "memory"
	}));
}
function resolveMemoryBackendConfig(params) {
	const backend = params.cfg.memory?.backend ?? DEFAULT_BACKEND;
	const citations = params.cfg.memory?.citations ?? DEFAULT_CITATIONS;
	if (backend !== "qmd") return {
		backend: "builtin",
		citations
	};
	const workspaceDir = resolveAgentWorkspaceDir(params.cfg, params.agentId);
	const qmdCfg = params.cfg.memory?.qmd;
	const includeDefaultMemory = qmdCfg?.includeDefaultMemory !== false;
	const nameSet = /* @__PURE__ */ new Set();
	const collections = [...resolveDefaultCollections(includeDefaultMemory, workspaceDir, nameSet), ...resolveCustomPaths(qmdCfg?.paths, workspaceDir, nameSet)];
	const rawCommand = qmdCfg?.command?.trim() || "qmd";
	return {
		backend: "qmd",
		citations,
		qmd: {
			command: splitShellArgs(rawCommand)?.[0] || rawCommand.split(/\s+/)[0] || "qmd",
			collections,
			includeDefaultMemory,
			sessions: resolveSessionConfig(qmdCfg?.sessions, workspaceDir),
			update: {
				intervalMs: resolveIntervalMs(qmdCfg?.update?.interval),
				debounceMs: resolveDebounceMs(qmdCfg?.update?.debounceMs),
				onBoot: qmdCfg?.update?.onBoot !== false,
				embedIntervalMs: resolveEmbedIntervalMs(qmdCfg?.update?.embedInterval)
			},
			limits: resolveLimits(qmdCfg?.limits),
			scope: qmdCfg?.scope ?? DEFAULT_QMD_SCOPE
		}
	};
}

//#endregion
//#region src/memory/search-manager.ts
const log = createSubsystemLogger("memory");
const QMD_MANAGER_CACHE = /* @__PURE__ */ new Map();
async function getMemorySearchManager(params) {
	const resolved = resolveMemoryBackendConfig(params);
	if (resolved.backend === "qmd" && resolved.qmd) {
		const cacheKey = buildQmdCacheKey(params.agentId, resolved.qmd);
		const cached = QMD_MANAGER_CACHE.get(cacheKey);
		if (cached) return { manager: cached };
		try {
			const { QmdMemoryManager } = await import("./qmd-manager-B8kpTnEx.js");
			const primary = await QmdMemoryManager.create({
				cfg: params.cfg,
				agentId: params.agentId,
				resolved
			});
			if (primary) {
				const wrapper = new FallbackMemoryManager({
					primary,
					fallbackFactory: async () => {
						const { MemoryIndexManager } = await import("./manager-BjJodZLC.js").then((n) => n.t);
						return await MemoryIndexManager.get(params);
					}
				}, () => QMD_MANAGER_CACHE.delete(cacheKey));
				QMD_MANAGER_CACHE.set(cacheKey, wrapper);
				return { manager: wrapper };
			}
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			log.warn(`qmd memory unavailable; falling back to builtin: ${message}`);
		}
	}
	try {
		const { MemoryIndexManager } = await import("./manager-BjJodZLC.js").then((n) => n.t);
		return { manager: await MemoryIndexManager.get(params) };
	} catch (err) {
		return {
			manager: null,
			error: err instanceof Error ? err.message : String(err)
		};
	}
}
var FallbackMemoryManager = class {
	constructor(deps, onClose) {
		this.deps = deps;
		this.onClose = onClose;
		this.fallback = null;
		this.primaryFailed = false;
	}
	async search(query, opts) {
		if (!this.primaryFailed) try {
			return await this.deps.primary.search(query, opts);
		} catch (err) {
			this.primaryFailed = true;
			this.lastError = err instanceof Error ? err.message : String(err);
			log.warn(`qmd memory failed; switching to builtin index: ${this.lastError}`);
			await this.deps.primary.close?.().catch(() => {});
		}
		const fallback = await this.ensureFallback();
		if (fallback) return await fallback.search(query, opts);
		throw new Error(this.lastError ?? "memory search unavailable");
	}
	async readFile(params) {
		if (!this.primaryFailed) return await this.deps.primary.readFile(params);
		const fallback = await this.ensureFallback();
		if (fallback) return await fallback.readFile(params);
		throw new Error(this.lastError ?? "memory read unavailable");
	}
	status() {
		if (!this.primaryFailed) return this.deps.primary.status();
		const fallbackStatus = this.fallback?.status();
		const fallbackInfo = {
			from: "qmd",
			reason: this.lastError ?? "unknown"
		};
		if (fallbackStatus) {
			const custom = fallbackStatus.custom ?? {};
			return {
				...fallbackStatus,
				fallback: fallbackInfo,
				custom: {
					...custom,
					fallback: {
						disabled: true,
						reason: this.lastError ?? "unknown"
					}
				}
			};
		}
		const primaryStatus = this.deps.primary.status();
		const custom = primaryStatus.custom ?? {};
		return {
			...primaryStatus,
			fallback: fallbackInfo,
			custom: {
				...custom,
				fallback: {
					disabled: true,
					reason: this.lastError ?? "unknown"
				}
			}
		};
	}
	async sync(params) {
		if (!this.primaryFailed) {
			await this.deps.primary.sync?.(params);
			return;
		}
		await (await this.ensureFallback())?.sync?.(params);
	}
	async probeEmbeddingAvailability() {
		if (!this.primaryFailed) return await this.deps.primary.probeEmbeddingAvailability();
		const fallback = await this.ensureFallback();
		if (fallback) return await fallback.probeEmbeddingAvailability();
		return {
			ok: false,
			error: this.lastError ?? "memory embeddings unavailable"
		};
	}
	async probeVectorAvailability() {
		if (!this.primaryFailed) return await this.deps.primary.probeVectorAvailability();
		return await (await this.ensureFallback())?.probeVectorAvailability() ?? false;
	}
	async close() {
		await this.deps.primary.close?.();
		await this.fallback?.close?.();
		this.onClose?.();
	}
	async ensureFallback() {
		if (this.fallback) return this.fallback;
		const fallback = await this.deps.fallbackFactory();
		if (!fallback) {
			log.warn("memory fallback requested but builtin index is unavailable");
			return null;
		}
		this.fallback = fallback;
		return this.fallback;
	}
};
function buildQmdCacheKey(agentId, config) {
	return `${agentId}:${stableSerialize(config)}`;
}
function stableSerialize(value) {
	return JSON.stringify(sortValue(value));
}
function sortValue(value) {
	if (Array.isArray(value)) return value.map((entry) => sortValue(entry));
	if (value && typeof value === "object") {
		const sortedEntries = Object.keys(value).toSorted((a, b) => a.localeCompare(b)).map((key) => [key, sortValue(value[key])]);
		return Object.fromEntries(sortedEntries);
	}
	return value;
}

//#endregion
//#region src/memory/index.ts
var memory_exports = /* @__PURE__ */ __exportAll({ getMemorySearchManager: () => getMemorySearchManager });

//#endregion
export { getMemorySearchManager as n, resolveMemoryBackendConfig as r, memory_exports as t };