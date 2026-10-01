// Импорт записи в библиотеке встреч (шаг 4): отказы браузера и сервера, загрузка,
// обработка, готово, ошибка, перетаскивание файла. Конвейера обработки на стенде
// нет: задание импорта — синтетика с причиной.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { containsText, exactText, type Translate } from "../i18n/texts.ts";
import { hold, rateLimited, reply } from "./overrides.ts";
import type { Override, State, StateContext } from "./types.ts";

const LIBRARY = "meetings/library";
const IMPORT = "/v1/me/sessions/import";
const JOB = "parity-import-job";
const MIB = 1024 * 1024;
/** Подстановка, которую фронтенд форматирует сам (размер): маркер — текст до неё. */
const SLOT = "\u0000";

interface Upload {
  readonly name: string;
  readonly mimeType: string;
  readonly bytes: number;
}

const RECORDING: Upload = { name: "Созвон с Acme.mp3", mimeType: "audio/mpeg", bytes: 4096 };

async function upload(page: Page, { t }: StateContext, file: Upload): Promise<void> {
  await page
    .locator(`input[aria-label=${JSON.stringify(t("meetings:meet.import.fileInputAria"))}]`)
    .setInputFiles({ name: file.name, mimeType: file.mimeType, buffer: Buffer.alloc(file.bytes, 1) });
}

function importState(id: string, file: Upload, overrides: readonly Override[], marker: (t: Translate) => string): State {
  return {
    id: `meetings.library.import-${id}`,
    fixture: LIBRARY,
    scope: "single",
    overrides,
    act: async (page, context) => upload(page, context, file),
    marker,
  };
}

const refused = (status: number, detail: string): Override =>
  reply("POST", IMPORT, status, { detail }, "отказ импорта; ответ — api/me_sessions*.py черновика");

const accepted = reply("POST", IMPORT, 202, { jobId: JOB }, "запись уходит в S3 и конвейер, которых на стенде нет");

function job(stage: string, progress: number): Override {
  const body: JsonValue = { id: JOB, fileName: RECORDING.name, stage, progress, meetingId: null, error: null };
  return reply("GET", `${IMPORT}/${JOB}`, 200, body, "ход задания импорта задаёт конвейер обработки");
}

export const MEETINGS_IMPORT_STATES: readonly State[] = [
  importState("refusal-format", { name: "Заметки.txt", mimeType: "text/plain", bytes: 64 }, [],
    (t) => exactText(t("meetings:meet.import.errFormat", { ext: "txt" }))),
  importState("refusal-empty", { name: "Пусто.mp3", mimeType: "audio/mpeg", bytes: 0 }, [],
    (t) => exactText(t("meetings:meet.import.errEmpty"))),
  importState("refusal-too-large", { name: "Большой.mp3", mimeType: "audio/mpeg", bytes: 26 * MIB }, [],
    (t) => containsText(t("meetings:meet.import.errTooLarge", { size: SLOT }).split(SLOT)[0] ?? "")),
  importState("refusal-quota", RECORDING, [refused(402, "minutes_exhausted")], (t) => exactText(t("meetings:meet.errors.quotaMinutes"))),
  importState("refusal-rate", RECORDING, [rateLimited("POST", IMPORT, "5 per 1 minute")],
    (t) => exactText(t("meetings:meet.errors.tooManyRequests"))),
  importState("refusal-storage", RECORDING, [refused(503, "storage_unavailable")], (t) => exactText(t("meetings:meet.import.errStorage"))),
  importState("refusal-no-logs", RECORDING, [refused(422, "import_unavailable_no_logs")],
    (t) => exactText(t("meetings:meet.import.errNoLogs"))),
  importState("uploading", RECORDING, [hold("POST", IMPORT)], (t) => exactText(t("meetings:meet.import.stageUploading"))),
  importState("processing", RECORDING, [accepted, job("transcribing", 0.4)], (t) => exactText(t("meetings:meet.import.stageTranscribing"))),
  importState("ready", RECORDING, [accepted, job("ready", 1)], (t) => exactText(t("meetings:meet.import.dismiss"))),
  importState("failed", RECORDING, [accepted, job("failed", 1)], (t) => exactText(t("meetings:meet.import.failed"))),
  {
    // Перетаскивание настоящего файла: событие с DataTransfer, в котором есть файл.
    id: "meetings.library.import-dragover",
    fixture: LIBRARY,
    scope: "single",
    act: async (page) =>
      page.locator("[data-onboarding='meetings-upload']").evaluate((panel) => {
        const transfer = new DataTransfer();
        transfer.items.add(new File(["x"], "call.mp3", { type: "audio/mpeg" }));
        panel.dispatchEvent(new DragEvent("dragenter", { bubbles: true, cancelable: true, dataTransfer: transfer }));
      }),
    marker: () => "[data-onboarding='meetings-upload'].border-foreground",
  },
];
