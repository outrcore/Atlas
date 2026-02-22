import { fn as sendMessageTelegram, jn as sendMessageSlack, kn as sendMessageWhatsApp, pn as sendMessageDiscord, ut as sendMessageIMessage } from "./reply-dpzhSRJz.js";
import { b as sendMessageSignal } from "./deliver-DvSIaDs_.js";

//#region src/cli/deps.ts
function createDefaultDeps() {
	return {
		sendMessageWhatsApp,
		sendMessageTelegram,
		sendMessageDiscord,
		sendMessageSlack,
		sendMessageSignal,
		sendMessageIMessage
	};
}
function createOutboundSendDeps(deps) {
	return {
		sendWhatsApp: deps.sendMessageWhatsApp,
		sendTelegram: deps.sendMessageTelegram,
		sendDiscord: deps.sendMessageDiscord,
		sendSlack: deps.sendMessageSlack,
		sendSignal: deps.sendMessageSignal,
		sendIMessage: deps.sendMessageIMessage
	};
}

//#endregion
export { createOutboundSendDeps as n, createDefaultDeps as t };