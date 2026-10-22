/*
 * Предложенные действия Leo (Action Gateway, ADR 0025; Leo §5.3, §8.4): Leo ничего не пишет без согласия —
 * сначала карточка с превью от сервера, потом «Одобрить» или «Отклонить». Пока бэкенда `agent` нет, действия
 * отдают моки разработки на маршрутах Leo §13.2.
 */

/** proposed → approved → executing → succeeded | partially_succeeded | failed; иначе rejected | expired. */
export type ProposalStatus =
  | "proposed"
  | "executing"
  | "succeeded"
  | "partially_succeeded"
  | "failed"
  | "rejected"
  | "expired"
  | "outcome_unknown";

/** Откуда просьба: чат, поручение (errand) или внешний клиент через MCP. */
export type ProposalOrigin = { kind: "thread" | "errand" | "mcp"; app: string | null };

/** Можно ли отыграть назад: отменить, компенсировать или нельзя совсем. */
export type Reversibility = "reversible" | "compensable" | "irreversible";

/** Кусок пословного сравнения: без изменений или замена (удалить `remove`, вставить `insert`). */
export type DiffSegment = { type: "equal"; text: string } | { type: "change"; remove: string; insert: string };

/** Превью считает сервер, а не модель: поля действия или правки текста. */
export type ProposalPreview =
  | { kind: "fields"; fields: { label: string; value: string }[]; body: string | null }
  | { kind: "diff"; target: string; segments: DiffSegment[] };

export type LeoProposal = {
  id: string;
  /** Инструмент, например `mail.send` или `notes.update`; по нему выбирается значок. */
  tool: string;
  title: string;
  /** Куда пишет действие: «Personal» или workspace. */
  space: string;
  origin: ProposalOrigin;
  reversibility: Reversibility;
  /** Карточка с предупреждением: подтверждать только на экране, внимательно. */
  warning: boolean;
  /** Действие готовилось по внешнему тексту (письмо, веб): человек видит, по чему именно. */
  taint: string | null;
  preview: ProposalPreview;
  status: ProposalStatus;
  /** Итог, когда действие выполнено или не удалось, — от сервера. */
  outcome: string | null;
  created_at: string;
  expires_at: string;
  resolved_at: string | null;
};

export const isPending = (proposal: Pick<LeoProposal, "status">) => proposal.status === "proposed";

/** Ид карточки одобрения на странице: к ней ведёт «Ждёт вашего одобрения» из дайджеста. */
export const proposalCardId = (proposalId: string) => `leo-proposal-${proposalId}`;

/** Номера замен в превью-сравнении: по ним человек выбирает, какие принять. */
export const changeIndexes = (segments: readonly DiffSegment[]) =>
  segments.flatMap((segment, index) => (segment.type === "change" ? [index] : []));

/** Текст после решения: принятые замены — новым текстом, остальные — как было. */
export function appliedText(segments: readonly DiffSegment[], accepted: ReadonlySet<number>): string {
  return segments
    .map((segment, index) => {
      if (segment.type === "equal") return segment.text;
      return accepted.has(index) ? segment.insert : segment.remove;
    })
    .join("");
}

/** Ключ сегмента для списка: вид и начало в исходном тексте. Стабилен, пока превью то же. */
export function segmentKeys(segments: readonly DiffSegment[]): string[] {
  const keys: string[] = [];
  let at = 0;
  for (const segment of segments) {
    keys.push(`${segment.type}:${at}`);
    at += (segment.type === "equal" ? segment.text : segment.remove).length;
  }
  return keys;
}
