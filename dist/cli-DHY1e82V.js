import { o as createSubsystemLogger } from "./entry.js";
import "./auth-profiles-CYBuGiBb.js";
import "./utils-DX85MiPR.js";
import "./exec-B8JKbXKW.js";
import { c as resolveDefaultAgentId, s as resolveAgentWorkspaceDir } from "./agent-scope-C9VjJXEK.js";
import "./github-copilot-token-SLWintYd.js";
import "./pi-model-discovery-DzEIEgHL.js";
import { i as loadConfig } from "./config-BoIfSsEL.js";
import "./manifest-registry-C69Z-I4v.js";
import "./server-context-fHEcd_eR.js";
import "./errors-aEe1_KOk.js";
import "./control-service-6F7uGLcn.js";
import "./client-DTTapxAX.js";
import "./call-ArM5G_0c.js";
import "./message-channel-PD-Bt0ux.js";
import "./links-ht4RDGt6.js";
import "./plugins-DqNdnGMR.js";
import "./logging-D-Jq2wIo.js";
import "./accounts-C_oSUhLd.js";
import { t as loadOpenClawPlugins } from "./loader-CT-eGFpU.js";
import "./progress-CmhSgg6x.js";
import "./prompt-style-DkSrWvZw.js";
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

//#region src/plugins/cli.ts
const log = createSubsystemLogger("plugins");
function registerPluginCliCommands(program, cfg) {
	const config = cfg ?? loadConfig();
	const workspaceDir = resolveAgentWorkspaceDir(config, resolveDefaultAgentId(config));
	const logger = {
		info: (msg) => log.info(msg),
		warn: (msg) => log.warn(msg),
		error: (msg) => log.error(msg),
		debug: (msg) => log.debug(msg)
	};
	const registry = loadOpenClawPlugins({
		config,
		workspaceDir,
		logger
	});
	const existingCommands = new Set(program.commands.map((cmd) => cmd.name()));
	for (const entry of registry.cliRegistrars) {
		if (entry.commands.length > 0) {
			const overlaps = entry.commands.filter((command) => existingCommands.has(command));
			if (overlaps.length > 0) {
				log.debug(`plugin CLI register skipped (${entry.pluginId}): command already registered (${overlaps.join(", ")})`);
				continue;
			}
		}
		try {
			const result = entry.register({
				program,
				config,
				workspaceDir,
				logger
			});
			if (result && typeof result.then === "function") result.catch((err) => {
				log.warn(`plugin CLI register failed (${entry.pluginId}): ${String(err)}`);
			});
			for (const command of entry.commands) existingCommands.add(command);
		} catch (err) {
			log.warn(`plugin CLI register failed (${entry.pluginId}): ${String(err)}`);
		}
	}
}

//#endregion
export { registerPluginCliCommands };