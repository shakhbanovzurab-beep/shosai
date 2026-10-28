import { type Room, RoomEvent } from "livekit-client";

import { boardApi } from "../api/board-api";
import type { BoardScene, BoardSession, BoardState } from "../domain/board";
import { sceneTooLarge } from "../domain/board";
import {
  type BoardFile,
  type BoardMessage,
  CURSOR_EVERY_MS,
  HELLO_WAIT_MS,
  versionSum,
} from "../domain/board-protocol";
import { BoardPatches, wholeScene } from "./board-patches";
import { BoardPictures } from "./board-picture";
import { BoardPresence } from "./board-presence";
import { BoardSaver } from "./board-saver";
import { streamBoard } from "./board-stream";
import { BoardWire } from "./board-wire";

/*
 * Доска звонка на LiveKit (MR-D13). Правки расходятся по каналу данных не чаще раза в 80 мс, только элементы новых
 * версий; опоздавший здоровается, и сохраняющий присылает ему сцену. Сохраняет и кладёт картинку в хранилище
 * владельца тот, чья идентичность меньше среди открывших доску; во время записи он же показывает её дорожкой.
 */

export type BoardLink = { room: Room; roomId: () => string; roomPass: string; nameOf: (identity: string) => string };

const filesById = (files: readonly BoardFile[]) => Object.fromEntries(files.map((file) => [file.id, file]));

export class LiveKitBoard implements BoardSession {
  private current: BoardState = { save: "loading", readOnly: false, cursors: [], streams: false };
  private readonly listeners = new Set<() => void>();
  private readonly remotes = new Set<(scene: BoardScene) => void>();
  private readonly presence: BoardPresence;
  private readonly wire: BoardWire;
  private readonly saver: BoardSaver;
  private readonly patches: BoardPatches;
  private readonly pictures: BoardPictures;
  private latest: BoardScene = { elements: [], files: {} };
  private phase: "closed" | "open" = "closed";
  // Правок, которых ещё нет на сервере: их сохраняет тот, кто сохраняет доску сейчас.
  private unsaved = 0;
  private loadedSum = 0;
  private pointedAt = 0;

  constructor(private readonly link: BoardLink) {
    this.presence = new BoardPresence(() => link.room.localParticipant.identity, link.nameOf);
    this.wire = new BoardWire(link.room, {
      message: (message, from) => this.receive(message, from),
      cursor: (from, x, y) => this.point(from, x, y),
      left: (identity) => this.forget(identity),
    });
    this.saver = new BoardSaver({
      save: (scene, version) => boardApi.save(link.roomId(), link.roomPass, scene, version),
      report: (save) => this.update({ save }),
      saved: (version) => this.wire.send({ kind: "saved", version }),
      stale: () => this.latestFromServer(),
    });
    this.patches = new BoardPatches(
      () => this.latest,
      (message) => this.wire.send(message),
    );
    this.pictures = new BoardPictures(
      () => this.latest,
      (picture) => boardApi.upload(link.roomId(), link.roomPass, picture),
    );
    link.room.on(RoomEvent.RecordingStatusChanged, () => this.update({}));
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  state = () => this.current;

  async load() {
    if (this.phase === "closed") {
      this.phase = "open";
      this.presence.open();
      this.wire.open();
      this.wire.send({ kind: "hello" });
      window.setTimeout(() => this.takeOver(), HELLO_WAIT_MS);
    }
    this.update({ save: "loading" });
    const saved = await boardApi.scene(this.link.roomId(), this.link.roomPass);
    this.saver.adopt(saved.version);
    this.loadedSum = versionSum(saved.elements);
    this.patches.seenScene(saved);
    this.update({ save: "saved" });
    return saved;
  }

  change(scene: BoardScene) {
    // До загрузки на холсте пустая сцена: сохранить её — значит затереть доску на сервере.
    if (this.current.readOnly || this.phase === "closed" || this.current.save === "loading") return;
    this.latest = scene;
    if (sceneTooLarge(scene)) return this.update({ save: "too_large" });
    this.patches.queue();
    if (versionSum(scene.elements) !== this.loadedSum) this.unsaved += 1;
    this.takeOver();
  }

  /** Человек взял свежую доску после второго конфликта подряд: сохранение начинается заново. */
  reload = () => this.saver.resume();

  private async latestFromServer() {
    const saved = await boardApi.scene(this.link.roomId(), this.link.roomPass);
    this.saver.adopt(saved.version);
    this.emit(saved);
  }

  pointer(x: number, y: number) {
    const now = Date.now();
    if (this.phase === "closed" || now - this.pointedAt < CURSOR_EVERY_MS) return;
    this.pointedAt = now;
    this.wire.cursor(x, y);
  }

  onRemote(listener: (scene: BoardScene) => void) {
    this.remotes.add(listener);
    return () => this.remotes.delete(listener);
  }

  stream = (container: HTMLElement) => streamBoard(this.link.room.localParticipant, container);

  async close() {
    if (this.phase === "closed") return;
    this.patches.flush();
    this.wire.send({ kind: "bye" });
    this.wire.close();
    const saving = this.presence.saves();
    this.phase = "closed";
    this.presence.close();
    this.update({ cursors: [] });
    if (saving) await Promise.all([this.saver.flush(), this.pictures.flush()]);
  }

  end() {
    this.saver.stop();
    this.patches.stop();
    this.pictures.stop();
    if (this.phase === "open") this.wire.close();
    this.phase = "closed";
    this.update({ readOnly: true, cursors: [] });
  }

  private receive(message: BoardMessage, from: string) {
    if (message.kind === "patch" || message.kind === "scene") {
      this.patches.seen(message.elements, message.files);
      return this.emit({ elements: message.elements, files: filesById(message.files) });
    }
    if (message.kind === "hello") {
      this.wire.send({ kind: "here" }, [from]);
      // Отвечает тот, кто сохранял до прихода нового: у пришедшего сцены ещё нет, даже если сохранять станет он.
      if (this.presence.saves()) this.wire.send({ kind: "scene", ...wholeScene(this.latest) }, [from]);
    }
    if (message.kind === "hello" || message.kind === "here") this.presence.joined(from);
    if (message.kind === "bye") return this.forget(from);
    if (message.kind === "saved") this.saver.adopt(message.version);
    // Сохранил другой: правки этого участника у него уже есть.
    const others = message.kind === "saved" && !this.presence.saves();
    if (others) this.unsaved = 0;
    this.update(others ? { save: "saved" } : {});
  }

  private point(from: string, x: number, y: number) {
    if (this.phase === "closed") return;
    this.presence.point(from, x, y);
    this.update({ cursors: this.presence.cursors() });
  }

  private forget(identity: string) {
    if (this.presence.left(identity)) this.update({ cursors: this.presence.cursors() });
    this.takeOver();
  }

  // Сохраняющий сохраняет всё, чего ещё нет на сервере: свою правку, слитую чужую или оставшуюся от ушедшего.
  private takeOver() {
    if (this.unsaved === 0 || !this.presence.saves()) return;
    this.unsaved = 0;
    this.saver.schedule(this.latest);
    this.pictures.touch();
    this.update({});
  }

  private emit(scene: BoardScene) {
    for (const listener of this.remotes) listener(scene);
  }

  private update(change: Partial<BoardState>) {
    const streams =
      this.phase === "open" && !this.current.readOnly && this.link.room.isRecording && this.presence.saves();
    this.current = { ...this.current, ...change, streams };
    for (const listener of this.listeners) listener();
  }
}
