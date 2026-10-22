"use client";

import { toast } from "sonner";

import { stickersApi } from "../api/stickers-api";
import { cardsWithout, cardsWithValues, valuesOn } from "../domain/field-rules";
import type { BoardSticker, CustomSticker, PlaceSticker, StickerPatch } from "../domain/stickers-contract";
import type { StopwatchAutomations } from "../domain/time-contract";
import type { BoardSnapshot } from "./board-store";
import { boardResource } from "./boards-resource";
import { boardIdOf, type CommandContext } from "./command-context";
import { ownedStickersResource } from "./stickers-resource";
import { describeProblem } from "./words";

/*
 * Поля доски из настроек: показать на карточках, поставить своё с другой доски или новое, поправить, снять с доски,
 * удалить совсем. Показ и снятие видны сразу, отказ возвращает только их; правка и удаление ждут сервера (диалог
 * показывает, что сохраняет).
 */

type Stickers = BoardSnapshot["stickers"];

export function createFieldCommands(ctx: CommandContext) {
  const fail = (error: unknown) => {
    const { t, ta } = ctx.words();
    toast.error(t("errors.saveChange"), { description: describeProblem(error, ta) });
  };
  const setStickers = (change: (list: Stickers) => Stickers) =>
    ctx.store.update((s) => ({ ...s, stickers: change(s.stickers) }));
  const refreshOwned = () => void ownedStickersResource.reload();
  const send = <T>(work: Promise<T>) => ctx.store.track(work);

  return {
    async setVisible(id: string, visible: boolean) {
      const show = (shown: boolean) =>
        setStickers((list) => list.map((s) => (s.id === id ? { ...s, visible: shown } : s)));
      show(visible);
      try {
        await send(stickersApi.patchOnBoard(boardIdOf(ctx), id, { visible }));
        return true;
      } catch (error) {
        show(!visible);
        fail(error);
        return false;
      }
    },
    /** Автоматизации секундомера доски (KT-D2): видны сразу, отказ возвращает прежние. */
    async setAutomations(automations: StopwatchAutomations) {
      const before = ctx.store.get().stickers.find((s) => s.id === "stopwatch")?.automations;
      const put = (value: StopwatchAutomations | undefined) =>
        setStickers((list) => list.map((s) => (s.id === "stopwatch" ? { ...s, automations: value } : s)));
      put(automations);
      try {
        await send(stickersApi.patchOnBoard(boardIdOf(ctx), "stopwatch", { automations }));
        return true;
      } catch (error) {
        put(before);
        fail(error);
        return false;
      }
    },
    /** Своё поле с другой доски или новое: встаёт последним и видно на карточках. */
    async place(request: PlaceSticker) {
      try {
        const placed = await send(stickersApi.place(boardIdOf(ctx), request));
        setStickers((list) => (list.some((s) => s.id === placed.id) ? list : [...list, placed]));
        // Значения, которые задачи доски уже несут, приходят с доской.
        if ("sticker_id" in request) void boardResource(boardIdOf(ctx)).reload();
        refreshOwned();
        return placed;
      } catch (error) {
        fail(error);
        return null;
      }
    },
    /** Имя и состояния; пропавшие состояния уходят с карточек вместе со значениями. */
    async edit(sticker: CustomSticker, patch: StickerPatch) {
      try {
        const saved = await send(stickersApi.patch(sticker.id, patch));
        const kept = new Set(saved.states.map((state) => state.id));
        ctx.store.update((s) => ({
          ...s,
          stickers: s.stickers.map((item) => (item.id === saved.id ? { ...saved, visible: item.visible } : item)),
          cards: saved.kind === "states" ? cardsWithout(s.cards, saved.id, (state) => kept.has(state)) : s.cards,
        }));
        refreshOwned();
        return true;
      } catch (error) {
        fail(error);
        return false;
      }
    },
    /** Снять с доски: значения остаются у задач и вернутся, если поле поставить снова. */
    async takeOff(sticker: BoardSticker) {
      const before = ctx.store.get();
      const index = before.stickers.findIndex((s) => s.id === sticker.id);
      const values = valuesOn(before.cards, sticker.id);
      ctx.store.update((s) => ({
        ...s,
        stickers: s.stickers.filter((item) => item.id !== sticker.id),
        cards: cardsWithout(s.cards, sticker.id),
      }));
      try {
        await send(stickersApi.takeOff(boardIdOf(ctx), sticker.id));
        refreshOwned();
        return true;
      } catch (error) {
        ctx.store.update((s) => ({
          ...s,
          stickers: s.stickers.some((item) => item.id === sticker.id)
            ? s.stickers
            : s.stickers.toSpliced(index, 0, sticker),
          cards: cardsWithValues(s.cards, sticker.id, values),
        }));
        fail(error);
        return false;
      }
    },
    /** Удалить поле совсем: со всех досок и его значения у всех задач (после подтверждения). */
    async remove(sticker: CustomSticker) {
      try {
        await send(stickersApi.remove(sticker.id));
        ctx.store.update((s) => ({
          ...s,
          stickers: s.stickers.filter((item) => item.id !== sticker.id),
          cards: cardsWithout(s.cards, sticker.id),
        }));
        refreshOwned();
        return true;
      } catch (error) {
        fail(error);
        return false;
      }
    },
  };
}

export type FieldCommands = ReturnType<typeof createFieldCommands>;
