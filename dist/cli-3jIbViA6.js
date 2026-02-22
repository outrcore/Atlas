import "./pi-embedded-helpers-yp9nTa28.js";
import { rt as loadOpenClawPlugins } from "./reply-dpzhSRJz.js";
import "./paths-scjhy7N2.js";
import { t as createSubsystemLogger } from "./subsystem-CAq3uyo7.js";
import "./utils-CKSrBNwq.js";
import "./exec-HEWTMJ7j.js";
import { c as resolveDefaultAgentId, s as resolveAgentWorkspaceDir } from "./agent-scope-CMs5Y7l-.js";
import "./model-selection-DMUrNhQP.js";
import "./github-copilot-token-pGSmVaW-.js";
import "./boolean-BgXe2hyu.js";
import "./env-0_mKbEWW.js";
import { i as loadConfig } from "./config-BgesjbOU.js";
import "./manifest-registry-DHaa1SJb.js";
import "./plugins-BUOltOVc.js";
import "./sandbox-DRFM-VuR.js";
import "./image-CeOzom1Z.js";
import "./pi-model-discovery-EwKVHlZB.js";
import "./chrome-DXeEqzlO.js";
import "./skills-CJ7mwV4S.js";
import "./routes-BRAgjbC0.js";
import "./server-context-WLgtN8If.js";
import "./message-channel-D8bD438k.js";
import "./logging-kuFzZMsG.js";
import "./accounts-CnZyZGal.js";
import "./paths-dxnbLZuf.js";
import "./redact-CVRUv382.js";
import "./tool-display-BUbpcaio.js";
import "./deliver-DvSIaDs_.js";
import "./dispatcher-DR7gv8QL.js";
import "./memory-CZ3Y3KK-.js";
import "./manager-D6u5aECn.js";
import "./sqlite-wME36UET.js";
import "./channel-summary-YVQVIBBH.js";
import "./client-DDfckjfC.js";
import "./call-GukGvEdr.js";
import "./login-qr-Df8LoqTu.js";
import "./pairing-store-BY4G6jFd.js";
import "./links-CAUfP-NG.js";
import "./progress-D-Sn_vVh.js";
import "./pi-tools.policy-CxKU_Y6A.js";
import "./prompt-style-BaZUWMLj.js";
import "./pairing-labels-SHig9vz3.js";
import "./session-cost-usage-CjJbWqU0.js";
import "./control-service-DX_bhYiI.js";
import "./channel-selection-3MDmbeey.js";

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