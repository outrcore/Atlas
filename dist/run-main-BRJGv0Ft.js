import { c as enableConsoleCapture, i as normalizeEnv, n as isTruthyEnvValue, p as defaultRuntime } from "./entry.js";
import "./auth-profiles-CYBuGiBb.js";
import { d as resolveConfigDir } from "./utils-DX85MiPR.js";
import "./exec-B8JKbXKW.js";
import "./agent-scope-C9VjJXEK.js";
import "./github-copilot-token-SLWintYd.js";
import "./pi-model-discovery-DzEIEgHL.js";
import { A as VERSION } from "./config-BoIfSsEL.js";
import "./manifest-registry-C69Z-I4v.js";
import "./server-context-fHEcd_eR.js";
import { r as formatUncaughtError } from "./errors-aEe1_KOk.js";
import "./control-service-6F7uGLcn.js";
import { t as ensureOpenClawCliOnPath } from "./path-env-Mj23v3sw.js";
import "./tailscale-iX1Q6arn.js";
import "./auth-CtW7U26l.js";
import "./client-DTTapxAX.js";
import "./call-ArM5G_0c.js";
import "./message-channel-PD-Bt0ux.js";
import "./links-ht4RDGt6.js";
import "./plugin-auto-enable-CHkhbAMs.js";
import "./plugins-DqNdnGMR.js";
import "./logging-D-Jq2wIo.js";
import "./accounts-C_oSUhLd.js";
import { At as installUnhandledRejectionHandler } from "./loader-CT-eGFpU.js";
import "./progress-CmhSgg6x.js";
import "./prompt-style-DkSrWvZw.js";
import "./note-Da2uKq9f.js";
import "./clack-prompter-DeQcZRms.js";
import "./onboard-channels-Dy2I5cYI.js";
import "./archive-aSMUcOc6.js";
import "./skill-scanner-zyQDNAfr.js";
import "./installs-BPJZ6XvZ.js";
import "./memory-CPZGC-m4.js";
import "./manager-ccacsCTZ.js";
import "./paths-KDZeTcQQ.js";
import "./sqlite-Bea7mwdA.js";
import "./routes-CQf4mC6T.js";
import "./pi-embedded-helpers-CizXvh_5.js";
import "./deliver-CwOq1cLe.js";
import "./sandbox-BRrzsAPQ.js";
import "./channel-summary-hJu8wgNa.js";
import "./wsl-n1NEqH3x.js";
import "./skills-DOTGORo4.js";
import "./image-CqAz7fXr.js";
import "./redact-1PNP01B_.js";
import "./tool-display-BQi5RDhv.js";
import "./channel-selection-BCxRC-eR.js";
import "./session-cost-usage-BmiV__dT.js";
import "./commands-D1GThS5G.js";
import "./pairing-store-Q74JKTYG.js";
import "./login-qr-DjKL_qiO.js";
import "./pairing-labels-BBUBD3TS.js";
import "./channels-status-issues-DkP9obUc.js";
import { n as ensurePluginRegistryLoaded } from "./command-options-DLCj_6g_.js";
import { a as getCommandPath, c as getPrimaryCommand, d as hasHelpOrVersion } from "./register.subclis-eIpP9Ku-.js";
import "./completion-cli-C-DA9xaJ.js";
import "./gateway-rpc-B81pMevL.js";
import "./deps-DM9mW0bN.js";
import { h as assertSupportedRuntime } from "./daemon-runtime-DaQFqgu9.js";
import "./service-D0-Epg6G.js";
import "./systemd-Bn7qQV3U.js";
import "./service-audit-xn3QhmTj.js";
import "./table-dQAz_LIH.js";
import "./widearea-dns-WCoYXIls.js";
import "./audit-C-ly35r1.js";
import "./onboard-skills-BQyzqWTu.js";
import "./health-format-DG4pgRsz.js";
import "./update-runner-CcY-ssuk.js";
import "./github-copilot-auth-Bq-JAE-i.js";
import "./logging-DcQ6jftd.js";
import "./hooks-status-CwY7TcQv.js";
import "./status-BBwq_9WK.js";
import "./skills-status-DEVprZKn.js";
import "./tui-DB1io0yx.js";
import "./agent-BK5RmhHa.js";
import "./node-service-DIRoejB3.js";
import "./auth-health-DrkbOCzj.js";
import { a as findRoutedCommand, n as emitCliBanner, t as ensureConfigReady } from "./config-guard-CkViI-ir.js";
import "./help-format-BBZy5-Be.js";
import "./configure-lirpnRZS.js";
import "./systemd-linger-B9e246TA.js";
import "./doctor-CyR-dZh8.js";
import path from "node:path";
import process$1 from "node:process";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

//#region src/infra/dotenv.ts
function loadDotEnv(opts) {
	const quiet = opts?.quiet ?? true;
	dotenv.config({ quiet });
	const globalEnvPath = path.join(resolveConfigDir(process.env), ".env");
	if (!fs.existsSync(globalEnvPath)) return;
	dotenv.config({
		quiet,
		path: globalEnvPath,
		override: false
	});
}

//#endregion
//#region src/cli/route.ts
async function prepareRoutedCommand(params) {
	emitCliBanner(VERSION, { argv: params.argv });
	await ensureConfigReady({
		runtime: defaultRuntime,
		commandPath: params.commandPath
	});
	if (params.loadPlugins) ensurePluginRegistryLoaded();
}
async function tryRouteCli(argv) {
	if (isTruthyEnvValue(process.env.OPENCLAW_DISABLE_ROUTE_FIRST)) return false;
	if (hasHelpOrVersion(argv)) return false;
	const path = getCommandPath(argv, 2);
	if (!path[0]) return false;
	const route = findRoutedCommand(path);
	if (!route) return false;
	await prepareRoutedCommand({
		argv,
		commandPath: path,
		loadPlugins: route.loadPlugins
	});
	return route.run(argv);
}

//#endregion
//#region src/cli/run-main.ts
function rewriteUpdateFlagArgv(argv) {
	const index = argv.indexOf("--update");
	if (index === -1) return argv;
	const next = [...argv];
	next.splice(index, 1, "update");
	return next;
}
async function runCli(argv = process$1.argv) {
	const normalizedArgv = stripWindowsNodeExec(argv);
	loadDotEnv({ quiet: true });
	normalizeEnv();
	ensureOpenClawCliOnPath();
	assertSupportedRuntime();
	if (await tryRouteCli(normalizedArgv)) return;
	enableConsoleCapture();
	const { buildProgram } = await import("./program-Jdmov1wB.js");
	const program = buildProgram();
	installUnhandledRejectionHandler();
	process$1.on("uncaughtException", (error) => {
		console.error("[openclaw] Uncaught exception:", formatUncaughtError(error));
		process$1.exit(1);
	});
	const parseArgv = rewriteUpdateFlagArgv(normalizedArgv);
	const primary = getPrimaryCommand(parseArgv);
	if (primary) {
		const { registerSubCliByName } = await import("./register.subclis-eIpP9Ku-.js").then((n) => n.i);
		await registerSubCliByName(program, primary);
	}
	if (!(!primary && hasHelpOrVersion(parseArgv))) {
		const { registerPluginCliCommands } = await import("./cli-DHY1e82V.js");
		const { loadConfig } = await import("./config-BoIfSsEL.js").then((n) => n.t);
		registerPluginCliCommands(program, loadConfig());
	}
	await program.parseAsync(parseArgv);
}
function stripWindowsNodeExec(argv) {
	if (process$1.platform !== "win32") return argv;
	const stripControlChars = (value) => {
		let out = "";
		for (let i = 0; i < value.length; i += 1) {
			const code = value.charCodeAt(i);
			if (code >= 32 && code !== 127) out += value[i];
		}
		return out;
	};
	const normalizeArg = (value) => stripControlChars(value).replace(/^['"]+|['"]+$/g, "").trim();
	const normalizeCandidate = (value) => normalizeArg(value).replace(/^\\\\\\?\\/, "");
	const execPath = normalizeCandidate(process$1.execPath);
	const execPathLower = execPath.toLowerCase();
	const execBase = path.basename(execPath).toLowerCase();
	const isExecPath = (value) => {
		if (!value) return false;
		const normalized = normalizeCandidate(value);
		if (!normalized) return false;
		const lower = normalized.toLowerCase();
		return lower === execPathLower || path.basename(lower) === execBase || lower.endsWith("\\node.exe") || lower.endsWith("/node.exe") || lower.includes("node.exe") || path.basename(lower) === "node.exe" && fs.existsSync(normalized);
	};
	const filtered = argv.filter((arg, index) => index === 0 || !isExecPath(arg));
	if (filtered.length < 3) return filtered;
	const cleaned = [...filtered];
	if (isExecPath(cleaned[1])) cleaned.splice(1, 1);
	if (isExecPath(cleaned[2])) cleaned.splice(2, 1);
	return cleaned;
}

//#endregion
export { runCli };