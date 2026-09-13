import { pinpointMode } from "./pinpoint.js";
import { unshuffleMode } from "./unshuffle.js";
import { state } from "../state.js";

export const GAME_MODES = {
  pinpoint: pinpointMode,
  unshuffle: unshuffleMode,
};

/**
 * Retrieve the active GameMode strategy instance based on state.gameMode.
 * @returns {typeof pinpointMode | typeof unshuffleMode}
 */
export function getActiveMode() {
  return GAME_MODES[state.gameMode] || pinpointMode;
}

export { pinpointMode, unshuffleMode };
