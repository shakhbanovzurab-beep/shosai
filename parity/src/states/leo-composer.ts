// Виджет Leo, ввод и голос (шаг 5): поле, упоминания, вложения, запись и её
// распознавание, голосовой режим, напоминание и переход по ссылке напоминания.
// Голос и напоминания приходят кадрами веб-сокетов: их задаёт состояние.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, withText, type Translate } from "../i18n/texts.ts";
import { chatSideCalls, composer, launcher, leo, openPanel } from "./leo-common.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { SocketScript, State, StateContext } from "./types.ts";

const SEARCH = "/v1/me/search";
const VOICE = "/v1/ws/voice";

const attachInput = (t: Translate): string => `input[aria-label=${JSON.stringify(t("leo:meet.chat.attachInputAria", { max: 5 }))}]`;

async function attach(page: Page, context: StateContext, files: readonly { name: string; bytes: number; type: string }[]): Promise<void> {
  await openPanel(page, context);
  await page.locator(attachInput(context.t)).setInputFiles(
    files.map((file) => ({ name: file.name, mimeType: file.type, buffer: Buffer.alloc(file.bytes, 1) })),
  );
}

const pdf = (name: string, bytes = 2048): { name: string; bytes: number; type: string } => ({ name, bytes, type: "application/pdf" });

async function mention(page: Page, context: StateContext): Promise<void> {
  await openPanel(page, context);
  await page.locator(composer(context.t)).pressSequentially("Что по @Acm");
}

/**
 * Голосовой режим: кадры сервера сразу после подключения и ответ на первый звук
 * микрофона. Без `ready` сеанс так и остаётся в подключении.
 */
function voice(frames: readonly JsonValue[], afterClient: readonly JsonValue[] = []): SocketScript[] {
  return [{ path: VOICE, frames, afterClient, reason: "голос ведёт Gemini Live через сервер черновика; на стенде его нет" }];
}

const READY: JsonValue = { t: "ready" };

async function startVoice(page: Page, context: StateContext): Promise<void> {
  await openPanel(page, context);
  await page.getByRole("button", { name: context.t("leo:leo.capability.leo_voice_enabled"), exact: true }).click();
}

const cosmic = (phase: string): string => `.mtg-cosmic--${phase}`;
/** Длительность голосового сообщения: хватает на несколько блоков звука. */
const RECORDING_MS = 1000;

export const LEO_COMPOSER_STATES: readonly State[] = [
  leo("composer.filled", (t) => `button[aria-label=${JSON.stringify(t("leo:agent.send"))}]`, {
    overrides: chatSideCalls,
    act: async (page, context) => {
      await openPanel(page, context);
      await page.locator(composer(context.t)).fill("Подведи итоги встреч за неделю");
    },
  }),
  { ...leo("composer.free-no-voice", (t) => exactText(t("leo:agent.emptyTitle"))), fixture: "shell/home-free" },
  leo("composer.attachments", (t) => `button[aria-label=${JSON.stringify(t("leo:agent.removeAttachment", { name: "отчёт.pdf" }))}]`, {
    act: async (page, context) => attach(page, context, [pdf("отчёт.pdf")]),
  }),
  leo("composer.attach-error", (t) => withText("[role=alert]", t("leo:meet.chat.rejectUnsupported")), {
    expectsAlert: true,
    act: async (page, context) => attach(page, context, [{ name: "setup.exe", bytes: 1024, type: "application/octet-stream" }]),
  }),
  leo("composer.attach-full", (t) => `button[aria-label=${JSON.stringify(t("leo:meet.chat.attachLimitAria", { max: 5 }))}]`, {
    act: async (page, context) => attach(page, context, [1, 2, 3, 4, 5].map((index) => pdf(`отчёт-${index}.pdf`))),
  }),
  leo("mention.loading", (t) => withText(`[role=listbox][aria-label=${JSON.stringify(t("leo:leo.mention.aria"))}]`, t("leo:leo.mention.searching")), {
    overrides: [...chatSideCalls, hold("GET", SEARCH)],
    act: mention,
  }),
  leo("mention.results", () => '[role=option][aria-selected=true]:has-text("Acme")', {
    overrides: [...chatSideCalls, reply("GET", SEARCH, 200, {
      query: "Acm",
      total: 2,
      hits: [
        { domain: "hubs", id: "parity-hub", title: "Acme", subtitle: null, snippet: null, to: "/hub", icon: "grid" },
        { domain: "meetings", id: "parity-meeting", title: "Демо для клиента Acme", subtitle: null, snippet: null, to: "/meetings", icon: "mic" },
      ],
      unavailable: [],
    }, "упоминание ищет по данным персоны; запрос «Acm» не записан")],
    act: mention,
  }),
  leo("composer.recording", (t) => `[aria-label=${JSON.stringify(t("leo:meet.live.voiceCancel"))}]`, {
    act: async (page, context) => {
      await openPanel(page, context);
      await page.getByRole("button", { name: context.t("leo:meet.chat.record"), exact: true }).click();
    },
    mask: {
      selectors: (t) => {
        const recorder = `div:has(> button[aria-label=${JSON.stringify(t("leo:meet.live.voiceCancel"))}])`;
        return [`${recorder} > canvas`, `${recorder} > span.mono`];
      },
      reason: "волна записи и таймер идут по настоящему микрофону и часам",
    },
  }),
  leo("composer.dictate-error", (t) => withText("[role=alert]", t("leo:agent.dictateError")), {
    expectsAlert: true,
    overrides: [serverError("POST", "/v1/ai/dictate")],
    act: async (page, context) => {
      await openPanel(page, context);
      await page.getByRole("button", { name: context.t("leo:meet.chat.record"), exact: true }).click();
      // Запись длится по-настоящему: микрофон отдаёт звук в реальном времени, и
      // без него «Готово» вернуло бы поле ввода без распознавания.
      await page.waitForTimeout(RECORDING_MS);
      await page.getByRole("button", { name: context.t("leo:meet.live.voiceDone"), exact: true }).click();
    },
  }),
  leo("composer.dictating", (t) => `textarea[disabled][placeholder=${JSON.stringify(t("leo:agent.dictating"))}]`, {
    overrides: [hold("POST", "/v1/ai/dictate")],
    act: async (page, context) => {
      await openPanel(page, context);
      await page.getByRole("button", { name: context.t("leo:meet.chat.record"), exact: true }).click();
      await page.waitForTimeout(RECORDING_MS);
      await page.getByRole("button", { name: context.t("leo:meet.live.voiceDone"), exact: true }).click();
    },
  }),
  leo("voice.connecting", (t) => withText(cosmic("connecting"), t("leo:meet.chat.voiceState.connecting")), {
    sockets: voice([]),
    act: startVoice,
  }),
  leo("voice.listening", (t) => withText(cosmic("listening"), t("leo:meet.chat.voiceState.listening")), {
    scope: "full",
    sockets: voice([READY]),
    act: startVoice,
  }),
  leo("voice.speaking", (t) => withText(cosmic("speaking"), t("leo:meet.chat.voiceState.speaking")), {
    sockets: voice([READY], [{ t: "phase", phase: "speaking" }]),
    act: startVoice,
  }),
  leo("voice.consulting", (t) => withText(cosmic("consulting"), t("leo:meet.chat.voiceState.consulting")), {
    sockets: voice([READY], [{ t: "phase", phase: "consulting" }]),
    act: startVoice,
  }),
  // Голос идёт и со свёрнутой панелью: на кнопке Leo — зелёная точка.
  leo("launcher.voice-live", (t) => `${launcher(t)} span.pulse-y`, {
    sockets: voice([READY]),
    act: async (page, context) => {
      await startVoice(page, context);
      await page.locator(withText(cosmic("listening"), context.t("leo:meet.chat.voiceState.listening"))).waitFor();
      await page.getByRole("button", { name: context.t("leo:agent.close"), exact: true }).click();
    },
  }),
  leo("voice.error.minutes", (t) => withText(cosmic("error"), t("leo:meet.chat.voiceErr.minutesExhausted")), {
    sockets: voice([{ t: "error", code: "minutes_exhausted" }]),
    act: startVoice,
  }),
  leo("voice.error.upgrade", (t) => withText(cosmic("error"), t("leo:meet.chat.voiceErr.upgradeRequired")), {
    sockets: voice([{ t: "error", code: "upgrade_required" }]),
    act: startVoice,
  }),
  leo("voice.error.retry", (t) => withText(cosmic("error"), t("leo:meet.chat.voiceErr.retryLater")), {
    sockets: voice([{ t: "error", code: "retry_later" }]),
    act: startVoice,
  }),
  leo("voice.error.disabled", (t) => withText(cosmic("error"), t("leo:meet.chat.voiceErr.disabled")), {
    sockets: voice([{ t: "error", code: "voice_disabled" }]),
    act: startVoice,
  }),
  leo("voice.turn-in-chat", () => 'div.md-content:has-text("Встреча в 10:00")', {
    sockets: voice([READY], [{ t: "turn", user: "Что у меня сегодня?", assistant: "Встреча в 10:00 — планирование бюджета Q4." }]),
    act: startVoice,
  }),
  leo("reminder-toast", () => 'div.rise.fixed:has-text("Напоминаю")', {
    act: async () => undefined,
    sockets: [{
      path: "/v1/ws/user",
      frames: [{ type: "reminder.due", nudge_id: "parity-nudge", errand_id: "parity-errand", turn_text: "Напоминаю: в 16:00 созвон с Acme.", deliveries: { web: "parity-delivery" } }],
      reason: "напоминание присылает планировщик поручений; на стенде он выключен",
    }],
    overrides: [
      reply("POST", "/v1/proactive/nudges/{nudge_id}/voice", 404, { detail: "Not Found" }, "озвучку напоминания синтезирует модель; на стенде её нет"),
      reply("POST", "/v1/proactive/reminders/{errand_id}/voice", 404, { detail: "Not Found" }, "озвучку напоминания синтезирует модель; на стенде её нет"),
    ],
  }),
  leo("reminder.deeplink", () => 'div.md-content:has-text("созвон с Acme")', {
    url: "/app/analytics?reminder=parity-errand",
    act: async () => undefined,
    overrides: [reply("POST", "/v1/ai/agent/reminder-context", 200, { text: "Вы просили напомнить: в 16:00 созвон с Acme. Подготовить сводку?" },
      "текст напоминания пишет модель агента; на стенде её нет")],
  }),
];
