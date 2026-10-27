import type { SettingsPatch, UserSettings } from "../domain/settings-contract";

/*
 * In-memory stand-in for the settings backend, used when BACKEND_API_URL is unset. On globalThis so
 * every route bundle shares it; resets when the server restarts. Billing and usage samples are in demo-billing.ts.
 */

type State = { settings: UserSettings };

const shared = globalThis as typeof globalThis & { settingsDemo?: State };
shared.settingsDemo ??= { settings: { hotkeys: {} } };
const state = shared.settingsDemo;

export const getSettings = () => state.settings;

export function patchSettings(patch: SettingsPatch): UserSettings {
  state.settings = { ...state.settings, ...patch };
  return state.settings;
}
