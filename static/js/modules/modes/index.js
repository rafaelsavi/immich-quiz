import { pinpointMode } from "./pinpoint.js";
import { albumShuffleMode } from "./album_shuffle.js";
import { state } from "../state.js";

export const GAME_MODES = {
  pinpoint: pinpointMode,
  album_shuffle: albumShuffleMode,
};

/**
 * Retrieve the active GameMode strategy instance based on state.gameMode.
 * @returns {typeof pinpointMode | typeof albumShuffleMode}
 */
export function getActiveMode() {
  return GAME_MODES[state.gameMode] || pinpointMode;
}

export { pinpointMode, albumShuffleMode };
