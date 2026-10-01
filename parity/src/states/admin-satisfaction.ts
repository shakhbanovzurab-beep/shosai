// Удовлетворённость в админке и карточка опроса (шаг 7): сводка с разрезами и
// фильтрами, ошибка, пусто; «Посмотреть анкету» — администратор снимает свои
// ответы, и в углу экрана сразу появляется карточка опроса. Админ-тексты вшиты
// по-русски — только ru.
//
// Снятие ответов удаляет строки базы, а новая карточка пишет показ: оба ответа —
// синтетика. Карточку у пользователя черновик показывает через 25 секунд после
// открытия страницы — дольше съёмки; та же карточка видна здесь.

import type { Translate } from "../i18n/texts.ts";
import { button, choose } from "../ui/admin-ui.ts";
import { merged } from "./admin-dashboard.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State } from "./types.ts";

const RU: readonly string[] = ["ru"];
const OVERVIEW = "/v1/admin/satisfaction/overview";
const text = (value: string) => (): string => `text=${JSON.stringify(value)}`;

function satisfaction(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `admin.satisfaction.${id}`, fixture: "admin/satisfaction", scope: "single", languages: RU, marker, ...extra };
}

export const ADMIN_SATISFACTION_STATES: readonly State[] = [
  satisfaction("populated", text("Средняя оценка"), { scope: "full" }),
  satisfaction("loading", () => "div.py-16 svg.spin", { overrides: [hold("GET", OVERVIEW)] }),
  satisfaction("error", () => '[data-slot=empty-title]:has-text("Не удалось загрузить результаты")', {
    overrides: [serverError("GET", OVERVIEW)],
  }),
  satisfaction("empty", text("За выбранный период анкет не показывали"), {
    overrides: [merged("GET", OVERVIEW, { shown: 0, answered: 0, dismissed: 0 }, "в засеве есть анкеты")],
  }),
  satisfaction("trend-empty", text("Ответов за период нет."), {
    overrides: [merged("GET", OVERVIEW, { trend: [] }, "в засеве есть ответы за период")],
  }),
  satisfaction("segment-empty", text("Ответов нет."), {
    reveal: true,
    overrides: [merged("GET", OVERVIEW, { by_language: [] }, "в засеве есть ответы на двух языках")],
  }),
  satisfaction("filter-days", () => '[role=combobox]:has-text("30 дней")', {
    act: async (page) => choose(page, "90 дней", "30 дней"),
  }),
  satisfaction("filter-users-only", () => '[role=combobox]:has-text("Только пользователи")', {
    act: async (page) => choose(page, "Все ответы", "Только пользователи"),
  }),
  satisfaction("filter-gender", () => '[role=combobox]:has-text("Женщины")', {
    act: async (page) => choose(page, "Любой пол", "Женщины"),
  }),
  satisfaction("replay", (t) => `dialog[aria-label=${JSON.stringify(t("satisfaction:satisfaction.question"))}]`, {
    overrides: [
      reply("POST", "/v1/admin/satisfaction/replay", 200, { removed: 2 }, "снятие ответов удаляет строки базы; запись его не делала"),
      reply("POST", "/v1/satisfaction/prompt", 200, { due: true, survey_id: "00000000-0000-4000-8000-0000000000c1",
        next_due_at: "2026-08-06T12:00:00+00:00" }, "после снятия ответов черновик сразу показывает анкету и пишет показ"),
    ],
    act: async (page) => button(page, "Посмотреть анкету").click(),
  }),
];
