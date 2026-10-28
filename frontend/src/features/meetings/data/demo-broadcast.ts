import type {
  BroadcastMessage,
  BroadcastSession,
  BroadcastSnapshot,
  StageMember,
  StageRole,
} from "../domain/broadcast";
import type { CallPerson } from "../domain/call";
import type { CallSetup } from "../domain/call-session";
import { DemoCall } from "./demo-call";
import { demoPerson } from "./demo-people";

/*
 * Трансляция на моках разработки: сцена — демо-звонок, зал живёт по таймерам — зрители приходят, поднимают руки,
 * ждут впуска и пишут в чат. Ссылка `studio` открывает студию ведущего до эфира, остальные — эфир глазами зрителя.
 */

export type DemoBroadcastSetup = { title: string; role: StageRole | null; waitingRoom: boolean; call: CallSetup };

const AUDIENCE = ["Omar Haddad", "Lena Fischer", "Yuki Sato", "David Chen"];
const LINES = ["Great talk!", "Can you share the slides?", "Hello from Lisbon 👋", "How does this scale?"];

const memberOf = (person: CallPerson, role: StageRole, onAir = true): StageMember => ({
  principal: person.identity.split("__")[0] ?? person.identity,
  identity: person.identity,
  name: person.name,
  role,
  onAir,
});

export class DemoBroadcast implements BroadcastSession {
  readonly call: DemoCall;
  private state: BroadcastSnapshot;
  private readonly listeners = new Set<() => void>();
  private readonly timers: number[] = [];
  private turn = 0;
  private readonly name: string;

  constructor(setup: DemoBroadcastSetup) {
    this.name = setup.call.name;
    this.call = new DemoCall({ ...setup.call, token: "broadcast" });
    const [first, second, third, fourth] = [1, 2, 3, 4].map((index) => demoPerson(index));
    const self = { ...demoPerson(0), identity: setup.call.identity, name: setup.call.name };
    const stage = setup.role
      ? [memberOf(self, setup.role), memberOf(first, "cohost"), memberOf(second, "speaker")]
      : [memberOf(first, "host"), memberOf(second, "speaker"), memberOf(third, "speaker")];
    this.state = {
      status: setup.role ? "scheduled" : "live",
      title: setup.title,
      role: setup.role,
      members: [...stage, memberOf(fourth, "speaker", false)],
      viewers: setup.role ? 0 : 42,
      waitingRoom: setup.waitingRoom,
      hands: [],
      admissions: [],
      chat: [],
      hand: "down",
      startedAt: setup.role ? null : new Date().toISOString(),
    };
    this.schedule();
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  snapshot = () => this.state;

  start = async () => this.update({ status: "live", startedAt: new Date().toISOString(), viewers: 0 });
  end = async () => this.update({ status: "ended" });

  async sendChat(text: string) {
    this.say(this.name, text, true);
  }

  async raiseHand(raised: boolean) {
    this.update({ hand: raised ? "raised" : "down" });
    // Ведущий на моках зовёт на сцену через несколько секунд после поднятой руки.
    if (raised) this.later(5_000, () => this.state.hand === "raised" && this.update({ hand: "invited" }));
  }

  async acceptInvite() {
    const self = this.call.snapshot().people.find((person) => person.isLocal);
    if (!self) return;
    this.update({ role: "speaker", hand: "down", members: [...this.state.members, memberOf(self, "speaker")] });
  }

  async answerHand(id: string, invite: boolean) {
    const hand = this.state.hands.find((item) => item.id === id);
    const hands = this.state.hands.filter((item) => item.id !== id);
    const invited = hand && invite ? [memberOf(demoPerson(5, { name: hand.name, identity: id }), "speaker")] : [];
    this.update({ hands, members: [...this.state.members, ...invited] });
  }

  async admit(id: string, admitted: boolean) {
    const admissions = this.state.admissions.filter((item) => item.id !== id);
    this.update({ admissions, viewers: (this.state.viewers ?? 0) + (admitted ? 1 : 0) });
  }

  setOnAir = async (principal: string, on: boolean) => this.patchMember(principal, { onAir: on });
  setCohost = async (principal: string, cohost: boolean) =>
    this.patchMember(principal, { role: cohost ? "cohost" : "speaker" });

  async removeFromStage(principal: string) {
    this.update({ members: this.state.members.filter((member) => member.principal !== principal) });
  }

  leave() {
    for (const timer of this.timers) window.clearTimeout(timer);
    this.call.leave();
  }

  private schedule() {
    const every = (ms: number, task: () => void) =>
      this.timers.push(window.setInterval(() => this.state.status === "live" && task(), ms));
    every(4_000, () => this.update({ viewers: Math.min(99, (this.state.viewers ?? 0) + 3) }));
    every(7_000, () => {
      this.turn += 1;
      this.say(AUDIENCE[this.turn % AUDIENCE.length] ?? "Guest", LINES[this.turn % LINES.length] ?? "👍", false);
    });
    every(11_000, () => {
      if (this.state.hands.length >= 3) return;
      const name = AUDIENCE[(this.turn + 1) % AUDIENCE.length] ?? "Guest";
      const hand = { id: `hand-${Date.now()}`, principal: `guest-${this.turn}`, name, at: new Date().toISOString() };
      this.update({ hands: [...this.state.hands, hand] });
    });
    every(9_000, () => {
      if (!this.state.waitingRoom || this.state.admissions.length >= 3) return;
      const name = AUDIENCE[(this.turn + 2) % AUDIENCE.length] ?? "Guest";
      this.update({
        admissions: [...this.state.admissions, { id: `knock-${Date.now()}`, name, at: new Date().toISOString() }],
      });
    });
  }

  private say(author: string, text: string, mine: boolean) {
    const seq = (this.state.chat.at(-1)?.seq ?? 0) + 1;
    const fromStage = mine && this.state.role !== null;
    const message: BroadcastMessage = {
      id: `bc-${seq}`,
      seq,
      author,
      text,
      sentAt: new Date().toISOString(),
      fromStage,
      mine,
    };
    this.update({ chat: [...this.state.chat, message].slice(-200) });
  }

  private later(ms: number, task: () => void) {
    this.timers.push(window.setTimeout(task, ms));
  }

  private patchMember(principal: string, change: Partial<StageMember>) {
    const members = this.state.members.map((member) =>
      member.principal === principal ? { ...member, ...change } : member,
    );
    this.update({ members });
  }

  private update(change: Partial<BroadcastSnapshot>) {
    if (this.state.status === "ended") return;
    this.state = { ...this.state, ...change };
    for (const listener of this.listeners) listener();
  }
}
