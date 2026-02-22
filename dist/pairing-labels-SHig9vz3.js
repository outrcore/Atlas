import { s as getPairingAdapter } from "./pairing-store-BY4G6jFd.js";

//#region src/pairing/pairing-labels.ts
function resolvePairingIdLabel(channel) {
	return getPairingAdapter(channel)?.idLabel ?? "userId";
}

//#endregion
export { resolvePairingIdLabel as t };