import { type DataPacket_Kind, type RemoteParticipant, type Room, RoomEvent } from "livekit-client";

import {
  BOARD_TOPIC,
  type BoardMessage,
  boardMessageOf,
  boardPacket,
  CURSOR_TOPIC,
  cursorOf,
  cursorPacket,
} from "../domain/board-protocol";

/*
 * Доска поверх канала данных комнаты: сообщения — текстовым потоком `wb` (он сам режет большую сцену на пакеты),
 * курсоры — пакетами `wb.cursor` без гарантии доставки: потерянный кадр курсора дешевле задержанного.
 */

export type WireHandlers = {
  message(message: BoardMessage, from: string): void;
  cursor(from: string, x: number, y: number): void;
  left(identity: string): void;
};

export class BoardWire {
  constructor(
    private readonly room: Room,
    private readonly handlers: WireHandlers,
  ) {}

  open() {
    this.room.registerTextStreamHandler(
      BOARD_TOPIC,
      (reader, { identity }) => void this.read(reader.readAll(), identity),
    );
    this.room.on(RoomEvent.DataReceived, this.received).on(RoomEvent.ParticipantDisconnected, this.disconnected);
  }

  close() {
    this.room.unregisterTextStreamHandler(BOARD_TOPIC);
    this.room.off(RoomEvent.DataReceived, this.received).off(RoomEvent.ParticipantDisconnected, this.disconnected);
  }

  /** Сообщение всем открывшим доску или только адресатам. */
  send(message: BoardMessage, to?: string[]) {
    const options = { topic: BOARD_TOPIC, ...(to ? { destinationIdentities: to } : {}) };
    // Неушедшая правка доску не роняет: соседи получат элементы со следующей — правки сравниваются по версиям.
    void this.room.localParticipant.sendText(boardPacket(message), options).catch(() => undefined);
  }

  cursor(x: number, y: number) {
    void this.room.localParticipant
      .publishData(cursorPacket(x, y), { reliable: false, topic: CURSOR_TOPIC })
      .catch(() => undefined);
  }

  private async read(text: Promise<string>, from: string) {
    const message = boardMessageOf(await text.catch(() => ""));
    if (message && from !== this.room.localParticipant.identity) this.handlers.message(message, from);
  }

  private readonly received = (
    payload: Uint8Array,
    participant?: RemoteParticipant,
    _kind?: DataPacket_Kind,
    topic?: string,
  ) => {
    if (topic !== CURSOR_TOPIC || !participant) return;
    const point = cursorOf(payload);
    if (point) this.handlers.cursor(participant.identity, point.x, point.y);
  };

  private readonly disconnected = (participant: RemoteParticipant) => this.handlers.left(participant.identity);
}
