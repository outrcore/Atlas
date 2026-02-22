import { C as setVerbose, O as isRich, k as theme, n as isTruthyEnvValue, p as defaultRuntime } from "./entry.js";
import "./auth-profiles-CYBuGiBb.js";
import { n as replaceCliName, r as resolveCliName } from "./command-format-ayFsmwwz.js";
import "./utils-DX85MiPR.js";
import "./exec-B8JKbXKW.js";
import "./agent-scope-C9VjJXEK.js";
import "./github-copilot-token-SLWintYd.js";
import "./pi-model-discovery-DzEIEgHL.js";
import { A as VERSION } from "./config-BUOaEEN4.js";
import "./manifest-registry-C69Z-I4v.js";
import "./server-context-fHEcd_eR.js";
import "./errors-aEe1_KOk.js";
import "./control-service-Dnj1SIXW.js";
import "./tailscale-iX1Q6arn.js";
import "./auth-CtW7U26l.js";
import "./client-DTTapxAX.js";
import "./call-D0Q9xKag.js";
import "./message-channel-PD-Bt0ux.js";
import { t as formatDocsLink } from "./links-ht4RDGt6.js";
import "./plugin-auto-enable-CHkhbAMs.js";
import "./plugins-DqNdnGMR.js";
import "./logging-D-Jq2wIo.js";
import "./accounts-C_oSUhLd.js";
import "./loader-C10Z-_b5.js";
import "./progress-CmhSgg6x.js";
import "./prompt-style-DkSrWvZw.js";
import "./note-Da2uKq9f.js";
import "./clack-prompter-DeQcZRms.js";
import "./onboard-channels-BEiXV9yk.js";
import "./archive-aSMUcOc6.js";
import "./skill-scanner-zyQDNAfr.js";
import "./installs-BPJZ6XvZ.js";
import "./memory-CPZGC-m4.js";
import "./manager-ccacsCTZ.js";
import "./paths-KDZeTcQQ.js";
import "./sqlite-Bea7mwdA.js";
import "./routes-Y4Li42Ub.js";
import "./pi-embedded-helpers-Cn5uNcdX.js";
import "./deliver-mZlsPAm6.js";
import "./sandbox-Cww7Jyn-.js";
import "./channel-summary-DEfjBmka.js";
import "./wsl-DylxauhL.js";
import "./skills-CEWpwqV5.js";
import "./image-YJYmS0WX.js";
import "./redact-1PNP01B_.js";
import "./tool-display-BQi5RDhv.js";
import "./channel-selection-BCxRC-eR.js";
import "./session-cost-usage-BmiV__dT.js";
import "./commands-xLe8YQvN.js";
import "./pairing-store-Q74JKTYG.js";
import "./login-qr-DlOnLloY.js";
import "./pairing-labels-BBUBD3TS.js";
import "./channels-status-issues-DkP9obUc.js";
import { n as ensurePluginRegistryLoaded } from "./command-options-B-UzAffs.js";
import { n as resolveCliChannelOptions } from "./channel-options-B10xgQ0c.js";
import { a as getCommandPath, d as hasHelpOrVersion, l as getVerboseFlag } from "./register.subclis-eGfkvaDt.js";
import "./completion-cli-hb3CJDW3.js";
import "./gateway-rpc-D8UeTavw.js";
import "./deps-H2tCBABX.js";
import "./daemon-runtime-QsiCCdW4.js";
import "./service-D0-Epg6G.js";
import "./systemd-Bn7qQV3U.js";
import "./service-audit-B-ot0l-D.js";
import "./table-dQAz_LIH.js";
import "./widearea-dns-WCoYXIls.js";
import "./audit-oOgg0rXo.js";
import "./onboard-skills-DkBKPwqh.js";
import "./health-format-B4hXu53s.js";
import "./update-runner-BxF97-ZO.js";
import "./github-copilot-auth-Nh8Vm2uy.js";
import "./logging-DcQ6jftd.js";
import "./hooks-status-BmLCmaQA.js";
import "./status-CaUsVnYq.js";
import "./skills-status-DyWAU1pw.js";
import "./tui-BARJ3Tgd.js";
import "./agent-CRChmow3.js";
import "./node-service-DIRoejB3.js";
import { t as forceFreePort } from "./ports-Bfw0vcwh.js";
import "./auth-health-DrkbOCzj.js";
import { i as hasEmittedCliBanner, n as emitCliBanner, o as registerProgramCommands, r as formatCliBannerLine, t as ensureConfigReady } from "./config-guard-BoNcaIsh.js";
import "./help-format-BBZy5-Be.js";
import "./configure-CLUR3g0g.js";
import "./systemd-linger-B9e246TA.js";
import "./doctor-Cx1qNbI1.js";
import { Command } from "commander";

//#region src/cli/program/context.ts
function createProgramContext() {
	const channelOptions = resolveCliChannelOptions();
	return {
		programVersion: VERSION,
		channelOptions,
		messageChannelOptions: channelOptions.join("|"),
		agentChannelOptions: ["last", ...channelOptions].join("|")
	};
}

//#endregion
//#region src/cli/program/help.ts
const CLI_NAME = resolveCliName();
const EXAMPLES = [
	["openclaw channels login --verbose", "Link personal WhatsApp Web and show QR + connection logs."],
	["openclaw message send --target +15555550123 --message \"Hi\" --json", "Send via your web session and print JSON result."],
	["openclaw gateway --port 18789", "Run the WebSocket Gateway locally."],
	["openclaw --dev gateway", "Run a dev Gateway (isolated state/config) on ws://127.0.0.1:19001."],
	["openclaw gateway --force", "Kill anything bound to the default gateway port, then start it."],
	["openclaw gateway ...", "Gateway control via WebSocket."],
	["openclaw agent --to +15555550123 --message \"Run summary\" --deliver", "Talk directly to the agent using the Gateway; optionally send the WhatsApp reply."],
	["openclaw message send --channel telegram --target @mychat --message \"Hi\"", "Send via your Telegram bot."]
];
function configureProgramHelp(program, ctx) {
	program.name(CLI_NAME).description("").version(ctx.programVersion).option("--dev", "Dev profile: isolate state under ~/.openclaw-dev, default gateway port 19001, and shift derived ports (browser/canvas)").option("--profile <name>", "Use a named profile (isolates OPENCLAW_STATE_DIR/OPENCLAW_CONFIG_PATH under ~/.openclaw-<name>)");
	program.option("--no-color", "Disable ANSI colors", false);
	program.configureHelp({
		sortSubcommands: true,
		sortOptions: true,
		optionTerm: (option) => theme.option(option.flags),
		subcommandTerm: (cmd) => theme.command(cmd.name())
	});
	program.configureOutput({
		writeOut: (str) => {
			const colored = str.replace(/^Usage:/gm, theme.heading("Usage:")).replace(/^Options:/gm, theme.heading("Options:")).replace(/^Commands:/gm, theme.heading("Commands:"));
			process.stdout.write(colored);
		},
		writeErr: (str) => process.stderr.write(str),
		outputError: (str, write) => write(theme.error(str))
	});
	if (process.argv.includes("-V") || process.argv.includes("--version") || process.argv.includes("-v")) {
		console.log(ctx.programVersion);
		process.exit(0);
	}
	program.addHelpText("beforeAll", () => {
		if (hasEmittedCliBanner()) return "";
		const rich = isRich();
		return `\n${formatCliBannerLine(ctx.programVersion, { richTty: rich })}\n`;
	});
	const fmtExamples = EXAMPLES.map(([cmd, desc]) => `  ${theme.command(replaceCliName(cmd, CLI_NAME))}\n    ${theme.muted(desc)}`).join("\n");
	program.addHelpText("afterAll", ({ command }) => {
		if (command !== program) return "";
		const docs = formatDocsLink("/cli", "docs.openclaw.ai/cli");
		return `\n${theme.heading("Examples:")}\n${fmtExamples}\n\n${theme.muted("Docs:")} ${docs}\n`;
	});
}

//#endregion
//#region src/cli/program/preaction.ts
function setProcessTitleForCommand(actionCommand) {
	let current = actionCommand;
	while (current.parent && current.parent.parent) current = current.parent;
	const name = current.name();
	const cliName = resolveCliName();
	if (!name || name === cliName) return;
	process.title = `${cliName}-${name}`;
}
const PLUGIN_REQUIRED_COMMANDS = new Set([
	"message",
	"channels",
	"directory"
]);
function registerPreActionHooks(program, programVersion) {
	program.hook("preAction", async (_thisCommand, actionCommand) => {
		setProcessTitleForCommand(actionCommand);
		const argv = process.argv;
		if (hasHelpOrVersion(argv)) return;
		const commandPath = getCommandPath(argv, 2);
		if (!(isTruthyEnvValue(process.env.OPENCLAW_HIDE_BANNER) || commandPath[0] === "update" || commandPath[0] === "completion" || commandPath[0] === "plugins" && commandPath[1] === "update")) emitCliBanner(programVersion);
		const verbose = getVerboseFlag(argv, { includeDebug: true });
		setVerbose(verbose);
		if (!verbose) process.env.NODE_NO_WARNINGS ??= "1";
		if (commandPath[0] === "doctor" || commandPath[0] === "completion") return;
		await ensureConfigReady({
			runtime: defaultRuntime,
			commandPath
		});
		if (PLUGIN_REQUIRED_COMMANDS.has(commandPath[0])) ensurePluginRegistryLoaded();
	});
}

//#endregion
//#region src/cli/program/build-program.ts
function buildProgram() {
	const program = new Command();
	const ctx = createProgramContext();
	const argv = process.argv;
	configureProgramHelp(program, ctx);
	registerPreActionHooks(program, ctx.programVersion);
	registerProgramCommands(program, ctx, argv);
	return program;
}

//#endregion
export { buildProgram };