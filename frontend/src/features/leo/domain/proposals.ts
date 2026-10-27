/*
 * Предложенные действия Leo (Action Gateway, ADR 0025; Leo §5.3, §8.4): Leo ничего не пишет без согласия —
 * сначала карточка с превью от сервера, потом «Одобрить» или «Отклонить» с её `nonce` (`/v1/agent/actions*`).
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
  /** Метка внешнего текста, прочитанного до карточки (`mail`, `web`, `mcp:<сервер>` …): человек видит, по чему. */
  taint: string | null;
  /** Прочитанное прогоном было похоже на указания для Leo; у карточек старого API поля нет. */
  suspicious?: boolean;
  preview: ProposalPreview;
  status: ProposalStatus;
  /** Код неудачи пункта действия (`not_found`, `timeout` …), когда оно не удалось целиком. */
  outcome: string | null;
  /** Решение несёт его: сервер примет решение только по той карточке, которую человек видел. */
  nonce: string;
  created_at: string;
  expires_at: string;
  resolved_at: string | null;
  /** Данные кабинета, которые изменили удавшиеся пункты (`tasks`, `notes`, `files`); пусто, пока она не выполнена. */
  invalidates?: string[];
};

/** Карточка после решения и прогон, чей поток несёт итог и эпилог Leo. */
export type DecidedProposal = LeoProposal & { run_id: string | null };

export const isPending = (proposal: Pick<LeoProposal, "status">) => proposal.status === "proposed";

const RANK: Record<ProposalStatus, number> = {
  proposed: 0,
  executing: 1,
  succeeded: 2,
  partially_succeeded: 2,
  failed: 2,
  rejected: 2,
  expired: 2,
  outcome_unknown: 2,
};

/** Карточка решена и, если её одобрили, выполнена: её состояние больше не изменится. */
export const isSettled = (proposal: Pick<LeoProposal, "status">) => RANK[proposal.status] === RANK.succeeded;

/** Более позднее из двух известных состояний карточки: статус только идёт вперёд, при равных — свежее прочтённое. */
export const laterOf = (known: LeoProposal, fresh: LeoProposal) =>
  RANK[known.status] > RANK[fresh.status] ? known : fresh;

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
