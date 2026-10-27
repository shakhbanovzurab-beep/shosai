import type { MemorySummary } from "../domain/memory-contract";
import type { SettingsPatch, UserSettings } from "../domain/settings-contract";

/*
 * In-memory stand-in for the settings backend, used when BACKEND_API_URL is unset. On globalThis so
 * every route bundle shares it; resets when the server restarts. Billing and usage samples are in demo-billing.ts.
 * The summary is what Leo wrote, so it stays as written in every interface language.
 */

type State = {
  settings: UserSettings;
  /** The summary Leo wrote, without the user's notes. */
  summary: MemorySummary;
  /** What the user told Leo through "Ask or update", oldest first. */
  notes: string[];
};

const section = (title: string, body: string) => ({ title, body });

const shared = globalThis as typeof globalThis & { settingsDemo?: State };
shared.settingsDemo ??= {
  settings: {
    hotkeys: {},
  },
  summary: {
    sections: [
      section(
        "Work",
        "You work in a fintech team building backend services with FastAPI and PostgreSQL, and you care about reliable data flows and clear APIs.",
      ),
      section(
        "Goals",
        "You’re preparing for system design interviews at product companies and want to practise explaining trade-offs out loud.",
      ),
      section("How you like answers", "Concise and direct, with code in Python unless you say otherwise."),
    ],
    suggestions: [
      "What should I focus on before my system design interviews?",
      "Which of my projects best show my backend experience?",
      "Summarise how my preferences shape Leo’s answers.",
    ],
    updated_at: new Date(Date.now() - 19 * 3600000).toISOString(),
  },
  notes: [],
};
const state = shared.settingsDemo;

export const getSettings = () => state.settings;

export function patchSettings(patch: SettingsPatch): UserSettings {
  state.settings = { ...state.settings, ...patch };
  return state.settings;
}

/**
 * The summary as the user sees it: what Leo wrote, then the user's notes under `notesTitle`, which the
 * route words in the request's interface language.
 */
export function getSummary(notesTitle: string): MemorySummary {
  const { summary, notes } = state;
  if (notes.length === 0) return summary;
  return { ...summary, sections: [...summary.sections, section(notesTitle, notes.join("\n"))] };
}

/**
 * The demo has no model to answer or rewrite the summary, so it records what the user said as a note;
 * the backend should answer questions and fold updates into the text.
 */
export function addSummaryNote(message: string) {
  state.notes = [...state.notes, message];
  state.summary = { ...state.summary, updated_at: new Date().toISOString() };
}

export function refreshSummary() {
  state.summary = { ...state.summary, updated_at: new Date().toISOString() };
}
