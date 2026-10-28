import { broadcastApi, type LiveChatMessageOut, type LiveStateOut } from "../api/broadcast-api";
import {
  type BroadcastMessage,
  type BroadcastSession,
  type BroadcastSnapshot,
  type BroadcastTicket,
  mayModerate,
} from "../domain/broadcast";
import type { CallSetup } from "../domain/call-session";
import { LiveKitCall } from "./livekit-call";

/*
 * Трансляция на LiveKit (A12c): сцена и свои устройства — звонок комнаты трансляции, эфир, сцена, очереди и чат —
 * маршруты сервера. На топике `stream` сервер говорит только, что изменилось: состояние и чат перечитываются.
 */

type Access = NonNullable<BroadcastTicket["access"]>;
type Push = { v?: unknown; kind?: unknown };

const decoder = new TextDecoder();
// Скрытые зрители не видны остальным: ведущий узнаёт их число, перечитывая состояние во время эфира.
const VIEWERS_EVERY_MS = 20_000;

const messageOf = (item: LiveChatMessageOut): BroadcastMessage => ({
  id: `bc-${item.seq}`,
  seq: item.seq,
  author: item.author,
  text: item.text,
  sentAt: item.sent_at,
  fromStage: item.from_stage,
  mine: item.mine,
});

function snapshotOf(state: LiveStateOut, chat: BroadcastMessage[]): BroadcastSnapshot {
  return {
    status: state.status,
    title: state.title,
    role: state.role,
    members: state.members.map((seat) => ({ ...seat, onAir: seat.on_air })),
    viewers: state.viewers,
    waitingRoom: state.waiting_room,
    hands: state.hands.map((hand) => ({ id: hand.principal, principal: hand.principal, name: hand.name, at: hand.at })),
    admissions: state.admissions,
    chat,
    hand: state.hand,
    startedAt: state.started_at,
  };
}

export class LiveKitBroadcast implements BroadcastSession {
  readonly call: LiveKitCall;
  private state: BroadcastSnapshot;
  private readonly listeners = new Set<() => void>();
  private readonly access: Access;
  private phase: "on" | "left" = "on";
  private timer: number | undefined;

  constructor(
    private readonly token: string,
    private readonly ticket: BroadcastTicket & { access: Access },
    setup: CallSetup,
  ) {
    this.access = ticket.access;
    this.call = new LiveKitCall(setup);
    this.state = snapshotOf(
      {
        status: "scheduled",
        title: ticket.title,
        role: ticket.role,
        members: [],
        viewers: null,
        waiting_room: ticket.waitingRoom,
        hands: [],
        admissions: [],
        hand: "down",
        started_at: null,
      },
      [],
    );
    // Пакеты трансляции шлёт только сервер: пакет участника на этом топике не значит ничего.
    this.call.onData("stream", (payload, from) => (from === undefined ? void this.pushed(payload) : undefined));
    this.call.subscribe(() => {
      if (this.call.snapshot().status === "ended" && this.phase === "on") this.update({ status: "ended" });
    });
  }

  async connect() {
    await this.call.connect();
    await Promise.all([this.reread(), this.readChat()]);
    this.timer = window.setInterval(() => {
      if (mayModerate(this.state.role) && this.state.status === "live") void this.reread();
    }, VIEWERS_EVERY_MS);
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  snapshot = () => this.state;

  start = async () => this.after(broadcastApi.start(this.ticket.broadcastId ?? ""));
  end = async () => this.after(broadcastApi.end(this.ticket.broadcastId ?? ""));

  async sendChat(text: string) {
    const sent = await broadcastApi.say(this.token, this.access.roomPass, text, crypto.randomUUID());
    this.mergeChat([messageOf(sent)]);
  }

  raiseHand = async (raised: boolean) => this.after(broadcastApi.hand(this.token, this.access.roomPass, raised));
  acceptInvite = async () => this.after(broadcastApi.stepOnStage(this.token, this.access.roomPass));
  answerHand = async (principal: string, invite: boolean) =>
    this.after(broadcastApi.answerHand(this.token, this.access.roomPass, principal, invite));
  admit = async (knock: string, admitted: boolean) =>
    this.after(broadcastApi.admit(this.token, this.access.roomPass, knock, admitted));
  setOnAir = async (principal: string, onAir: boolean) =>
    this.after(broadcastApi.seat(this.token, this.access.roomPass, principal, { on_air: onAir }));
  setCohost = async (principal: string, cohost: boolean) =>
    this.after(broadcastApi.seat(this.token, this.access.roomPass, principal, { role: cohost ? "cohost" : "speaker" }));
  removeFromStage = async (principal: string) =>
    this.after(broadcastApi.unseat(this.token, this.access.roomPass, principal));

  leave() {
    this.phase = "left";
    window.clearInterval(this.timer);
    this.call.leave();
  }

  private async after(call: Promise<unknown>) {
    await call;
    await this.reread();
  }

  private async pushed(payload: Uint8Array) {
    let push: Push;
    try {
      push = JSON.parse(decoder.decode(payload)) as Push;
    } catch {
      return;
    }
    if (push.v !== 1) return;
    if (push.kind === "ended") return this.update({ status: "ended" });
    await (push.kind === "chat" ? this.readChat() : this.reread());
  }

  private async reread() {
    const state = await broadcastApi.state(this.token, this.access.roomPass).catch(() => null);
    if (state) this.update(snapshotOf(state, this.state.chat));
  }

  private async readChat() {
    const after = this.state.chat.at(-1)?.seq ?? 0;
    const page = await broadcastApi.chatAfter(this.token, this.access.roomPass, after).catch(() => null);
    this.mergeChat((page?.items ?? []).map(messageOf));
  }

  private mergeChat(messages: BroadcastMessage[]) {
    const known = new Set(this.state.chat.map((item) => item.seq));
    const added = messages.filter((item) => !known.has(item.seq));
    if (added.length > 0)
      this.update({ chat: [...this.state.chat, ...added].toSorted((a, b) => a.seq - b.seq).slice(-200) });
  }

  private update(change: Partial<BroadcastSnapshot>) {
    if (this.state.status === "ended") return;
    if (change.status === "ended") window.clearInterval(this.timer);
    this.state = { ...this.state, ...change };
    for (const listener of this.listeners) listener();
  }
}
