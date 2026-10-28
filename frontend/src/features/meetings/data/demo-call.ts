import { type CallPerson, initialsOf } from "../domain/call";
import type { CallSession, CallSetup, CallSnapshot, VideoKind } from "../domain/call-session";
import { mergeChat } from "../domain/chat-log";
import type { CallEnd } from "../domain/join";
import { admitReaction, REACTIONS, type Reaction, shownReactions } from "../domain/reactions";
import { demoCrowd, demoPerson } from "./demo-people";
import { demoCameraStream } from "./demo-video";

/*
 * Звонок на моках разработки: соединяется, люди говорят по очереди, кто-то поднимает руку, пишет в чат и
 * реагирует. Ссылка `flaky` показывает переподключение, `big` — звонок на 50. Свои камера и экран — настоящие.
 */

type Video = { stream: MediaStream; stop: () => void };

export class DemoCall implements CallSession {
  private state: CallSnapshot;
  private readonly listeners = new Set<() => void>();
  private readonly timers: number[] = [];
  private readonly videos = new Map<string, Video>();
  private screen: MediaStream | null = null;
  private sent: number[] = [];
  private turn = 0;

  constructor(private readonly setup: CallSetup) {
    const self: CallPerson = {
      ...demoPerson(0),
      identity: setup.identity,
      name: setup.name,
      isLocal: true,
      isOwner: setup.role === "owner",
      micOn: setup.media.mic,
      cameraOn: setup.media.camera,
    };
    const others = Array.from({ length: demoCrowd(setup.token) }, (_, index) => demoPerson(index + 1));
    if (setup.role !== "owner" && others[0]) others[0] = { ...others[0], isOwner: true };
    this.state = {
      status: "connecting",
      end: null,
      title: setup.title,
      role: setup.role,
      marks: setup.marks,
      self: setup.identity,
      people: [self, ...others],
      chat: [],
      reactions: [],
      link: setup.link,
    };
    this.schedule();
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  snapshot = () => this.state;

  setMic = (on: boolean) => this.patchPerson(this.setup.identity, { micOn: on });
  setCamera = (on: boolean) => this.patchPerson(this.setup.identity, { cameraOn: on });

  async setScreen(on: boolean) {
    if (!on) return this.stopScreen();
    if (!navigator.mediaDevices?.getDisplayMedia) return false;
    try {
      this.screen = await navigator.mediaDevices.getDisplayMedia({ video: true });
    } catch {
      // Отказ браузера или человека — показ просто не начинается.
      return false;
    }
    this.screen.getVideoTracks()[0]?.addEventListener("ended", () => void this.stopScreen());
    this.patchPerson(this.setup.identity, { screenOn: true });
    return true;
  }

  setHand(raised: boolean) {
    this.patchPerson(this.setup.identity, { hand: raised ? new Date().toISOString() : null });
  }

  react(emoji: Reaction) {
    const now = Date.now();
    const gate = admitReaction(this.sent, now);
    this.sent = gate.times;
    if (gate.admitted) this.show(emoji, this.setup.identity, now);
    return gate.admitted;
  }

  async sendChat(text: string) {
    this.say(this.setup.identity, this.setup.name, text);
  }

  async lowerHandOf(identity: string) {
    this.patchPerson(identity, { hand: null });
  }

  async remove(identity: string) {
    this.videos.get(identity)?.stop();
    this.videos.delete(identity);
    this.update({ people: this.state.people.filter((person) => person.identity !== identity) });
  }

  leave = () => this.finish("left");
  endForAll = async () => this.finish("ended");

  attach(identity: string, kind: VideoKind, element: HTMLVideoElement | null) {
    const stream = element ? this.streamOf(identity, kind) : null;
    // Тот же поток не переназначается: иначе видео мигает при каждой отрисовке.
    if (element && element.srcObject !== stream) element.srcObject = stream;
  }

  private streamOf(identity: string, kind: VideoKind): MediaStream | null {
    if (identity === this.setup.identity) return kind === "screen" ? this.screen : this.setup.media.stream;
    let video = this.videos.get(identity);
    const person = this.state.people.find((item) => item.identity === identity);
    if (!video && person) {
      video = demoCameraStream(identity, initialsOf(person.name)) ?? undefined;
      if (video) this.videos.set(identity, video);
    }
    return video?.stream ?? null;
  }

  private schedule() {
    const later = (ms: number, task: () => void) => this.timers.push(window.setTimeout(task, ms));
    const every = (ms: number, task: () => void) => this.timers.push(window.setInterval(task, ms));
    later(700, () => this.update({ status: "connected" }));
    every(2_600, () => this.nextSpeaker());
    later(5_000, () => this.byOther(1, (person) => this.say(person.identity, person.name, "Hi all 👋")));
    later(8_000, () =>
      this.byOther(2, (person) => this.patchPerson(person.identity, { hand: new Date().toISOString() })),
    );
    every(6_500, () =>
      this.byOther(this.turn, (person) => this.show(REACTIONS[this.turn % 6] ?? "👍", person.identity)),
    );
    if (this.setup.token === "flaky") {
      later(12_000, () => this.update({ status: "reconnecting" }));
      later(15_000, () => this.update({ status: "connected" }));
    }
  }

  private nextSpeaker() {
    this.turn += 1;
    const others = this.state.people.filter((person) => !person.isLocal);
    const speaker = others[this.turn % Math.min(others.length, 3)];
    const now = Date.now();
    this.update({
      people: this.state.people.map((person) => {
        const speaking = person.identity === speaker?.identity;
        return { ...person, speaking, lastSpokeAt: speaking ? now : person.lastSpokeAt };
      }),
    });
  }

  private byOther(index: number, act: (person: CallPerson) => void) {
    const others = this.state.people.filter((person) => !person.isLocal);
    const person = others[index % Math.max(others.length, 1)];
    if (person && this.state.status !== "ended") act(person);
  }

  private say(identity: string, author: string, text: string) {
    const seq = (this.state.chat.at(-1)?.seq ?? 0) + 1;
    const message = { id: `demo-${seq}`, seq, identity, author, text, sentAt: new Date().toISOString() };
    this.update({ chat: mergeChat(this.state.chat, [message]) });
  }

  private show(emoji: Reaction, from: string, at = Date.now()) {
    const reaction = { id: `${from}-${at}-${Math.random()}`, emoji, from, at };
    this.update({ reactions: shownReactions([...this.state.reactions, reaction], at) });
    const expire = () => this.update({ reactions: shownReactions(this.state.reactions, Date.now()) });
    this.timers.push(window.setTimeout(expire, 4_100));
  }

  private async stopScreen() {
    for (const track of this.screen?.getTracks() ?? []) track.stop();
    this.screen = null;
    this.patchPerson(this.setup.identity, { screenOn: false });
    return false;
  }

  private finish(end: CallEnd) {
    for (const timer of this.timers) window.clearTimeout(timer);
    for (const video of this.videos.values()) video.stop();
    void this.stopScreen();
    this.update({ status: "ended", end });
  }

  private patchPerson(identity: string, change: Partial<CallPerson>) {
    this.update({
      people: this.state.people.map((person) => (person.identity === identity ? { ...person, ...change } : person)),
    });
  }

  private update(change: Partial<CallSnapshot>) {
    if (this.state.status === "ended" && change.status !== "ended") return;
    this.state = { ...this.state, ...change };
    for (const listener of this.listeners) listener();
  }
}
