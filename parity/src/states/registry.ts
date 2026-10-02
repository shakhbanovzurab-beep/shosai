// Реестр состояний и правила его целостности. Новый раздел добавляет сюда свой
// список; правила проверяют юнит-тесты (registry.test.ts) в CI.

import { existsSync } from "node:fs";

import { fixturePath } from "../fixtures/format.ts";
import { cellsFor, type Cell } from "../matrix.ts";
import { ACCOUNT_STATES } from "./account.ts";
import { ACTIVITY_STATES } from "./activity.ts";
import { ADMIN_ANALYTICS_STATES } from "./admin-analytics.ts";
import { ADMIN_DASHBOARD_STATES } from "./admin-dashboard.ts";
import { ADMIN_FINANCE_STATES } from "./admin-finance.ts";
import { ADMIN_OPS_STATES } from "./admin-ops.ts";
import { ADMIN_SATISFACTION_STATES } from "./admin-satisfaction.ts";
import { ADMIN_USERS_STATES } from "./admin-users.ts";
import { ACCOUNT_ACTION_STATES } from "./account-actions.ts";
import { ACCOUNT_VARIANT_STATES } from "./account-variants.ts";
import { AUTH_STATES } from "./auth.ts";
import { AUTH_ERROR_STATES } from "./auth-errors.ts";
import { AUTH_FLOW_STATES } from "./auth-flows.ts";
import { BILLING_CARD_STATES } from "./billing-cards.ts";
import { BILLING_VARIANT_STATES } from "./billing-variants.ts";
import { ONBOARDING_VARIANT_STATES } from "./onboarding-variants.ts";
import { CALENDAR_STATES } from "./calendar.ts";
import { CALENDAR_INTEGRATION_STATES } from "./calendar-integrations.ts";
import { HUB_STATES } from "./hub.ts";
import { LEO_CABINET_STATES } from "./leo-cabinet.ts";
import { LEO_CHAT_STATES } from "./leo-chat.ts";
import { LEO_MEMORY_STATES } from "./leo-memory.ts";
import { LEO_COMPOSER_STATES } from "./leo-composer.ts";
import { LEO_STREAM_STATES } from "./leo-stream.ts";
import { MCP_STATES } from "./mcp.ts";
import { MEETINGS_DOC_STATES } from "./meetings-doc.ts";
import { MEETINGS_IMPORT_STATES } from "./meetings-import.ts";
import { MEETINGS_LIBRARY_STATES } from "./meetings-library.ts";
import { MEETINGS_PANEL_STATES } from "./meetings-panels.ts";
import { MEETINGS_SETUP_STATES } from "./meetings-setup.ts";
import { MEETINGS_SHARED_STATES } from "./meetings-shared.ts";
import { MEETINGS_TRANSCRIPT_STATES } from "./meetings-transcript.ts";
import { MODELS_STATES } from "./models.ts";
import { PALETTE_STATES } from "./palette.ts";
import { PROMPTS_STATES } from "./prompts.ts";
import { PROMPTS_EDITOR_STATES } from "./prompts-editor.ts";
import { SHELL_VARIANT_STATES } from "./shell-variants.ts";
import { STUDIO_CONTEXT_STATES } from "./studio-context.ts";
import { STUDIO_KNOWLEDGE_STATES } from "./studio-knowledge.ts";
import { ROOMS_STATES } from "./rooms.ts";
import { ROOMS_GUEST_STATES } from "./rooms-guest.ts";
import { ROOMS_PANEL_STATES } from "./rooms-panels.ts";
import { SHARED_FILES_STATES } from "./shared-files.ts";
import { STORAGE_STATES } from "./storage.ts";
import { STREAMS_STUDIO_STATES } from "./streams-studio.ts";
import { STREAMS_WATCH_STATES } from "./streams-watch.ts";
import { STORAGE_VIEWER_STATES } from "./storage-viewer.ts";
import { TRACKER_STATES } from "./tracker.ts";
import { TRACKER_BOARD_STATES } from "./tracker-board.ts";
import { stateLanguages, type State } from "./types.ts";

export const ALL_STATES: readonly State[] = [
  ...AUTH_STATES,
  ...AUTH_ERROR_STATES,
  ...AUTH_FLOW_STATES,
  ...ACCOUNT_STATES,
  ...ACCOUNT_VARIANT_STATES,
  ...ACCOUNT_ACTION_STATES,
  ...BILLING_VARIANT_STATES,
  ...BILLING_CARD_STATES,
  ...SHELL_VARIANT_STATES,
  ...PALETTE_STATES,
  ...ONBOARDING_VARIANT_STATES,
  ...MEETINGS_LIBRARY_STATES,
  ...MEETINGS_IMPORT_STATES,
  ...MEETINGS_DOC_STATES,
  ...MEETINGS_PANEL_STATES,
  ...MEETINGS_TRANSCRIPT_STATES,
  ...MEETINGS_SHARED_STATES,
  ...MEETINGS_SETUP_STATES,
  ...CALENDAR_STATES,
  ...CALENDAR_INTEGRATION_STATES,
  ...STUDIO_CONTEXT_STATES,
  ...STUDIO_KNOWLEDGE_STATES,
  ...LEO_CHAT_STATES,
  ...LEO_STREAM_STATES,
  ...LEO_COMPOSER_STATES,
  ...LEO_CABINET_STATES,
  ...LEO_MEMORY_STATES,
  ...MCP_STATES,
  ...PROMPTS_STATES,
  ...PROMPTS_EDITOR_STATES,
  ...MODELS_STATES,
  ...HUB_STATES,
  ...STORAGE_STATES,
  ...STORAGE_VIEWER_STATES,
  ...SHARED_FILES_STATES,
  ...TRACKER_STATES,
  ...TRACKER_BOARD_STATES,
  ...ROOMS_STATES,
  ...ROOMS_PANEL_STATES,
  ...ROOMS_GUEST_STATES,
  ...STREAMS_WATCH_STATES,
  ...STREAMS_STUDIO_STATES,
  ...ADMIN_DASHBOARD_STATES,
  ...ADMIN_ANALYTICS_STATES,
  ...ADMIN_USERS_STATES,
  ...ADMIN_FINANCE_STATES,
  ...ADMIN_OPS_STATES,
  ...ADMIN_SATISFACTION_STATES,
  ...ACTIVITY_STATES,
];

export function stateCells(state: State): Cell[] {
  return cellsFor(state.scope, stateLanguages(state), state.sweep ?? false, state.viewports);
}

/** Нарушения правил реестра; пустой список — реестр целостен. */
export function registryProblems(states: readonly State[], fixturesDir: string): string[] {
  const problems: string[] = [];
  const seen = new Set<string>();
  for (const state of states) {
    if (seen.has(state.id)) problems.push(`${state.id}: идентификатор повторяется`);
    seen.add(state.id);
    if (!/^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(state.id)) problems.push(`${state.id}: идентификатор не в виде раздел.экран.состояние`);
    if (stateCells(state).length === 0) problems.push(`${state.id}: ни одной ячейки съёмки`);
    // Фикстура нужна на языке фикстуры состояния и на языке каждой его ячейки:
    // прогон по языкам (sweep) снимает экран и на остальных 14.
    const languages = new Set([...stateLanguages(state), ...stateCells(state).map((cell) => cell.language)]);
    for (const language of languages) {
      if (!existsSync(fixturePath(fixturesDir, state.fixture, language))) {
        problems.push(`${state.id}: нет фикстуры ${state.fixture} на языке ${language}`);
      }
    }
    for (const override of state.overrides ?? []) {
      if (override.reason.trim() === "") problems.push(`${state.id}: переопределение ${override.path} без причины`);
      if (!override.path.startsWith("/v1/")) problems.push(`${state.id}: переопределение вне /v1: ${override.path}`);
    }
    if (state.mask !== undefined && state.mask.reason.trim() === "") problems.push(`${state.id}: маска без причины`);
    if (state.tolerance !== undefined && state.tolerance.reason.trim() === "") problems.push(`${state.id}: допуск без причины`);
    for (const socket of state.sockets ?? []) {
      if (socket.reason.trim() === "") problems.push(`${state.id}: сокет ${socket.path} без причины`);
    }
  }
  return problems;
}
