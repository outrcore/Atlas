import { k as theme, p as defaultRuntime } from "./entry.js";
import "./auth-profiles-CYBuGiBb.js";
import "./utils-DX85MiPR.js";
import "./exec-B8JKbXKW.js";
import "./agent-scope-C9VjJXEK.js";
import "./github-copilot-token-SLWintYd.js";
import "./config-BUOaEEN4.js";
import "./manifest-registry-C69Z-I4v.js";
import "./server-context-fHEcd_eR.js";
import "./errors-aEe1_KOk.js";
import "./client-DTTapxAX.js";
import "./call-D0Q9xKag.js";
import "./message-channel-PD-Bt0ux.js";
import { t as formatDocsLink } from "./links-ht4RDGt6.js";
import "./plugins-DqNdnGMR.js";
import "./logging-D-Jq2wIo.js";
import "./accounts-C_oSUhLd.js";
import "./paths-KDZeTcQQ.js";
import "./routes-Y4Li42Ub.js";
import "./pi-embedded-helpers-Cn5uNcdX.js";
import "./sandbox-Cww7Jyn-.js";
import "./channel-summary-DEfjBmka.js";
import "./skills-CEWpwqV5.js";
import "./redact-1PNP01B_.js";
import "./tool-display-BQi5RDhv.js";
import { t as parseTimeoutMs } from "./parse-timeout-D1XX_zN_.js";
import { t as runTui } from "./tui-BARJ3Tgd.js";

//#region src/cli/tui-cli.ts
function registerTuiCli(program) {
	program.command("tui").description("Open a terminal UI connected to the Gateway").option("--url <url>", "Gateway WebSocket URL (defaults to gateway.remote.url when configured)").option("--token <token>", "Gateway token (if required)").option("--password <password>", "Gateway password (if required)").option("--session <key>", "Session key (default: \"main\", or \"global\" when scope is global)").option("--deliver", "Deliver assistant replies", false).option("--thinking <level>", "Thinking level override").option("--message <text>", "Send an initial message after connecting").option("--timeout-ms <ms>", "Agent timeout in ms (defaults to agents.defaults.timeoutSeconds)").option("--history-limit <n>", "History entries to load", "200").addHelpText("after", () => `\n${theme.muted("Docs:")} ${formatDocsLink("/cli/tui", "docs.openclaw.ai/cli/tui")}\n`).action(async (opts) => {
		try {
			const timeoutMs = parseTimeoutMs(opts.timeoutMs);
			if (opts.timeoutMs !== void 0 && timeoutMs === void 0) defaultRuntime.error(`warning: invalid --timeout-ms "${String(opts.timeoutMs)}"; ignoring`);
			const historyLimit = Number.parseInt(String(opts.historyLimit ?? "200"), 10);
			await runTui({
				url: opts.url,
				token: opts.token,
				password: opts.password,
				session: opts.session,
				deliver: Boolean(opts.deliver),
				thinking: opts.thinking,
				message: opts.message,
				timeoutMs,
				historyLimit: Number.isNaN(historyLimit) ? void 0 : historyLimit
			});
		} catch (err) {
			defaultRuntime.error(String(err));
			defaultRuntime.exit(1);
		}
	});
}

//#endregion
export { registerTuiCli };