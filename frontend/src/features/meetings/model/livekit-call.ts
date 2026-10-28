import { type LocalTrackPublication, type RemoteParticipant, Room, RoomEvent, Track } from "livekit-client";

import { callApi } from "../api/call-api";
import {
  type CallSession,
  type CallSetup,
  type CallSnapshot,
  initialSnapshot,
  type VideoKind,
} from "../domain/call-session";
import { lastSeq, mergeChat } from "../domain/chat-log";
import type { Reaction } from "../domain/reactions";
import { roomMetadataOf } from "../domain/room-metadata";
import { endOf, incoming, publishLobbyTracks, stopTrack } from "./livekit-media";
import { callPeopleOf } from "./livekit-people";
import { ReactionDesk } from "./livekit-reactions";
import { TrackStage } from "./livekit-tracks";

/*
 * Звонок на LiveKit (meetings A10). Видео подписывается только для плиток на сцене — остальные не стоят ни трафика,
 * ни ядра SFU (meetings §1.3); звук — от всех. Чат идёт через маршрут сервера и приходит пакетом `chat`,
 * реакции — пакетами `reaction`, рука — атрибутом участника.
 */

export class LiveKitCall implements CallSession {
  private readonly room = new Room({ adaptiveStream: true, dynacast: true });
  private readonly listeners = new Set<() => void>();
  private readonly stage: TrackStage;
  private readonly reactions: ReactionDesk;
  private state: CallSnapshot;

  constructor(private readonly setup: CallSetup) {
    this.state = initialSnapshot(setup);
    this.stage = new TrackStage(this.room, setup.identity);
    this.reactions = new ReactionDesk((reactions) => this.update({ reactions }));
    this.listen();
  }

  /** Подключиться и опубликовать свои дорожки из лобби; выключенные — сразу заглушены. */
  async connect() {
    await this.room.connect(this.setup.livekit.url, this.setup.livekit.token, { autoSubscribe: false });
    await publishLobbyTracks(this.room.localParticipant, this.setup.media);
    for (const participant of this.room.remoteParticipants.values()) this.stage.subscribeAudio(participant);
    await this.room.startAudio();
    this.update({ status: "connected" });
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  snapshot = () => this.state;

  setMic = (on: boolean) => void this.toggle(Track.Source.Microphone, on);
  setCamera = (on: boolean) => void this.toggle(Track.Source.Camera, on);

  async setScreen(on: boolean) {
    const publication = await this.room.localParticipant.setScreenShareEnabled(on).catch(() => undefined);
    this.refresh();
    return on && publication !== undefined;
  }

  setHand(raised: boolean) {
    void this.room.localParticipant.setAttributes({ hand: raised ? new Date().toISOString() : "" });
  }

  react(emoji: Reaction) {
    const sent = this.reactions.send(emoji, this.setup.identity);
    if (sent) void this.room.localParticipant.publishData(sent, { reliable: false, topic: "reaction" });
    return sent !== null;
  }

  async sendChat(text: string) {
    const message = await callApi.say(this.roomId(), this.setup.roomPass, text, crypto.randomUUID());
    const sent = { ...message, sentAt: message.sent_at };
    this.update({ chat: mergeChat(this.state.chat, [sent]) });
  }

  lowerHandOf = (identity: string) => callApi.lowerHand(this.roomId(), identity);
  remove = (identity: string) => callApi.remove(this.roomId(), identity);
  leave = () => void this.room.disconnect();

  endForAll = async () => void (await callApi.end(this.roomId()));

  attach = (identity: string, kind: VideoKind, element: HTMLVideoElement | null) =>
    this.stage.attach(identity, kind, element);

  private listen() {
    const refresh = () => this.refresh();
    this.room
      .on(RoomEvent.ParticipantConnected, (participant) => {
        this.stage.subscribeAudio(participant);
        refresh();
      })
      .on(RoomEvent.TrackPublished, (publication, participant) => this.stage.want(publication, participant))
      .on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
        this.stage.show(track, participant.identity);
        refresh();
      })
      .on(RoomEvent.TrackUnsubscribed, stopTrack)
      .on(RoomEvent.LocalTrackPublished, (publication: LocalTrackPublication) => {
        this.stage.showLocal(publication);
        refresh();
      })
      .on(RoomEvent.DataReceived, (payload, participant, _kind, topic) => this.receive(payload, participant, topic))
      .on(RoomEvent.RoomMetadataChanged, refresh)
      .on(RoomEvent.Reconnecting, () => this.update({ status: "reconnecting" }))
      .on(RoomEvent.Reconnected, () => {
        this.update({ status: "connected" });
        void this.catchUp();
      })
      .on(RoomEvent.Disconnected, (reason) => this.update({ status: "ended", end: endOf(reason) }));
    for (const event of [
      RoomEvent.ParticipantDisconnected,
      RoomEvent.TrackMuted,
      RoomEvent.TrackUnmuted,
      RoomEvent.TrackUnpublished,
      RoomEvent.ActiveSpeakersChanged,
      RoomEvent.ParticipantAttributesChanged,
      RoomEvent.ParticipantNameChanged,
    ])
      this.room.on(event, refresh);
  }

  private receive(payload: Uint8Array, participant: RemoteParticipant | undefined, topic: string | undefined) {
    const { chat, reaction } = incoming(payload, participant?.identity, topic);
    if (chat) this.update({ chat: mergeChat(this.state.chat, [chat]) });
    if (reaction) this.reactions.receive(reaction.emoji, reaction.from);
  }

  private async catchUp() {
    const page = await callApi
      .chatAfter(this.roomId(), this.setup.roomPass, lastSeq(this.state.chat))
      .catch(() => null);
    const missed = (page?.items ?? []).map((item) => ({ ...item, sentAt: item.sent_at }));
    this.update({ chat: mergeChat(this.state.chat, missed) });
  }

  private async toggle(source: Track.Source, on: boolean) {
    const track = this.room.localParticipant.getTrackPublication(source)?.track;
    await (on ? track?.unmute() : track?.mute());
    this.refresh();
  }

  private roomId() {
    const id = this.setup.roomId ?? roomMetadataOf(this.room.metadata)?.roomId;
    if (!id) throw new Error("room id is unknown until the room's metadata arrives");
    return id;
  }

  private refresh() {
    const metadata = roomMetadataOf(this.room.metadata);
    const { localParticipant, remoteParticipants } = this.room;
    const people = callPeopleOf(localParticipant, remoteParticipants.values(), metadata?.owner ?? null);
    this.update({ people, marks: metadata?.marks ?? this.state.marks });
  }

  private update(change: Partial<CallSnapshot>) {
    if (this.state.status === "ended" && change.status !== "ended") return;
    this.state = { ...this.state, ...change };
    for (const listener of this.listeners) listener();
  }
}
