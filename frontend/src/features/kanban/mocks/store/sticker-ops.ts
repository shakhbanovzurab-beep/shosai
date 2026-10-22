import type { BoardStickerPatch } from "../../domain/stickers-contract";
import {
  BOARD_STICKERS_MAX,
  type BoardSticker,
  type CustomSticker,
  isSystemSticker,
  isTimeSticker,
  type OwnedSticker,
  type PlaceSticker,
  STICKER_NUMBER_LIMIT,
  STICKERS_MAX,
  type StickerPatch,
  type StickerUsage,
  type StickerValue,
} from "../../domain/stickers-contract";
import { ME_PERSON } from "../seed/builders";
import { fail, type Outcome, ok } from "./outcome";
import { demo, touch, touchTask } from "./state";
import type { StoredBoard, StoredTask } from "./types";

/*
 * Поля (KG-D4): поле принадлежит владельцу доски — в демо все доски личные, значит, человеку; значение — часть
 * задачи, его видит каждый, кто видит задачу.
 */

const MINE = { user_id: ME_PERSON.user_id };
const isMine = (sticker: CustomSticker) => "user_id" in sticker.owner && sticker.owner.user_id === MINE.user_id;
const withId = (states: { name: string; color: CustomSticker["states"][number]["color"]; id?: string }[]) =>
  states.map((s) => ({ id: s.id ?? crypto.randomUUID(), name: s.name, color: s.color }));

/** Сколько задач несут значение поля, всего и по состояниям. */
function usageOf(stickerId: string): StickerUsage {
  const usage: StickerUsage = { tasks: 0, states: {} };
  for (const values of demo().values.values()) {
    const value = values.get(stickerId);
    if (!value) continue;
    usage.tasks += 1;
    if ("state_id" in value) usage.states[value.state_id] = (usage.states[value.state_id] ?? 0) + 1;
  }
  return usage;
}

export function ownedStickers(): OwnedSticker[] {
  const d = demo();
  return [...d.stickers.values()].filter(isMine).map((sticker) => ({
    ...sticker,
    boards: [...d.boards.values()]
      .filter((board) => board.stickers.some((s) => s.id === sticker.id))
      .map((board) => ({ id: board.id, name: board.name })),
    usage: usageOf(sticker.id),
  }));
}

export function placeSticker(board: StoredBoard, request: PlaceSticker): Outcome<BoardSticker> {
  if (board.jira) return fail("jira_unsupported");
  if (board.stickers.length >= BOARD_STICKERS_MAX) return fail("board_stickers_full");
  const d = demo();
  let sticker: CustomSticker | undefined;
  if ("sticker_id" in request) {
    sticker = d.stickers.get(request.sticker_id);
    if (!sticker || !isMine(sticker)) return fail("sticker_not_found");
  } else {
    if ([...d.stickers.values()].filter(isMine).length >= STICKERS_MAX) return fail("stickers_full");
    const states = request.kind === "states" ? withId(request.states ?? []) : [];
    sticker = { id: crypto.randomUUID(), kind: request.kind, name: request.name, states, owner: MINE };
    d.stickers.set(sticker.id, sticker);
  }
  const placed = board.stickers.find((s) => s.id === sticker.id);
  if (!placed) board.stickers.push({ id: sticker.id, visible: true });
  touch(board);
  return ok({ ...sticker, visible: placed?.visible ?? true });
}

/** Набор состояний — полным списком: пропавшие состояния очищают значения, которые на них стояли. */
export function patchSticker(id: string, patch: StickerPatch): Outcome<CustomSticker> {
  const d = demo();
  const sticker = d.stickers.get(id);
  if (!sticker || !isMine(sticker)) return fail("sticker_not_found");
  if (patch.name !== undefined) sticker.name = patch.name;
  if (patch.states !== undefined && sticker.kind === "states") {
    const known = new Set(sticker.states.map((s) => s.id));
    if (patch.states.some((s) => s.id !== undefined && !known.has(s.id))) return fail("state_not_found");
    sticker.states = withId(patch.states);
    const kept = new Set(sticker.states.map((s) => s.id));
    for (const values of d.values.values()) {
      const value = values.get(id);
      if (value && "state_id" in value && !kept.has(value.state_id)) values.delete(id);
    }
  }
  for (const board of d.boards.values()) if (board.stickers.some((s) => s.id === id)) touch(board);
  return ok(sticker);
}

export function deleteSticker(id: string): Outcome<null> {
  const d = demo();
  const sticker = d.stickers.get(id);
  if (!sticker || !isMine(sticker)) return fail("sticker_not_found");
  d.stickers.delete(id);
  for (const values of d.values.values()) values.delete(id);
  for (const board of d.boards.values()) {
    const before = board.stickers.length;
    board.stickers = board.stickers.filter((s) => s.id !== id);
    if (board.stickers.length !== before) touch(board);
  }
  return ok(null);
}

/** Показ поля на карточках и автоматизации секундомера; полей времени на доске Jira нет (ADR 0061). */
export function patchBoardSticker(board: StoredBoard, id: string, patch: BoardStickerPatch): Outcome<null> {
  if (board.jira && isTimeSticker(id)) return fail("jira_unsupported");
  if (patch.automations && id !== "stopwatch") return fail("validation_error");
  if (patch.visible !== undefined) {
    if (isSystemSticker(id)) board.system[id] = patch.visible;
    else {
      const placed = board.stickers.find((s) => s.id === id);
      if (!placed) return fail("sticker_not_on_board");
      placed.visible = patch.visible;
    }
  }
  if (patch.automations) board.stopwatch = { ...patch.automations };
  touch(board);
  return ok(null);
}

/** Снять с доски: значения остаются у задач и вернутся, когда поле поставят снова. */
export function removeSticker(board: StoredBoard, id: string): Outcome<null> {
  if (isSystemSticker(id)) return fail("system_sticker");
  if (!board.stickers.some((s) => s.id === id)) return fail("sticker_not_on_board");
  board.stickers = board.stickers.filter((s) => s.id !== id);
  touch(board);
  return ok(null);
}

function valueProblem(sticker: CustomSticker, value: StickerValue) {
  if ("state_id" in value) {
    if (sticker.kind !== "states") return "value_kind_mismatch";
    return sticker.states.some((s) => s.id === value.state_id) ? null : "state_not_found";
  }
  if ("number" in value) {
    if (sticker.kind !== "number") return "value_kind_mismatch";
    const cents = Math.round(value.number * 100);
    return Math.abs(value.number) < STICKER_NUMBER_LIMIT && Math.abs(cents - value.number * 100) < 1e-6
      ? null
      : "validation_error";
  }
  return sticker.kind === "text" ? null : "value_kind_mismatch";
}

/** Новое значение — только у поля, которое человек может ставить (своё) или которое задача уже несёт. */
export function putValue(task: StoredTask, stickerId: string, value: StickerValue): Outcome<StickerValue> {
  if (task.jira) return fail("jira_unsupported");
  const d = demo();
  const sticker = d.stickers.get(stickerId);
  const values = d.values.get(task.id) ?? new Map<string, StickerValue>();
  if (!sticker || (!isMine(sticker) && !values.has(stickerId))) return fail("sticker_not_found");
  const problem = valueProblem(sticker, value);
  if (problem) return fail(problem);
  d.values.set(task.id, values.set(stickerId, value));
  touchTask(task.id);
  return ok(value);
}

export function clearValue(task: StoredTask, stickerId: string): Outcome<null> {
  if (!demo().stickers.has(stickerId)) return fail("sticker_not_found");
  demo().values.get(task.id)?.delete(stickerId);
  touchTask(task.id);
  return ok(null);
}
