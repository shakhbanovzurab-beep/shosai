import { useEffect, useEffectEvent, useRef, useState } from "react";

import type { SessionStatus } from "@/features/identity/domain/session";
import { useSession } from "@/features/identity/model/session-store";
import { ApiError } from "@/lib/api/errors";

import type { BroadcastSession, BroadcastTicket } from "../domain/broadcast";
import { type JoinProblem, joinProblemOf } from "../domain/join";
import type { LocalMedia } from "./local-media";
import { enterBroadcast, knockAgain, openBroadcast } from "./open-broadcast";

/*
 * Путь от ссылки трансляции до эфира: имя гостя, ответ ссылки; сцена — через лобби со своими устройствами, зал —
 * сразу смотреть, а из зала ожидания — когда впустят. «Ещё не в эфире», «мест нет» и «закончилась» — свои страницы.
 */

export type BroadcastFlow =
  | { step: "waiting" }
  | { step: "name" }
  | { step: "joining" }
  | { step: "lobby"; ticket: BroadcastTicket; name: string }
  | { step: "knocking"; ticket: BroadcastTicket; name: string }
  | { step: "outside"; ticket: BroadcastTicket }
  | { step: "live"; session: BroadcastSession }
  | { step: "problem"; problem: JoinProblem };

// Зритель в зале ожидания спрашивает о впуске раз в 3 с.
const KNOCK_EVERY_MS = 3_000;

/** Шаг, который видит страница: пока сессия ждёт ответа, гость уже называет себя. */
const shownFlow = (flow: BroadcastFlow, status: SessionStatus): BroadcastFlow =>
  flow.step === "waiting" && status === "signed-out" ? { step: "name" } : flow;

const problemOf = (error: unknown) =>
  error instanceof ApiError ? joinProblemOf(error.status, error.code) : joinProblemOf(0, null);

export function useBroadcastFlow(token: string, media: LocalMedia) {
  const session = useSession();
  const [flow, setFlow] = useState<BroadcastFlow>({ step: "waiting" });
  const started = useRef(false);
  const signedName = session.me ? (session.me.display_name ?? session.me.full_name) : "";

  async function open(ticket: BroadcastTicket, name: string) {
    try {
      const self = { name, media: { mic: media.mic, camera: media.camera, stream: media.stream } };
      setFlow({ step: "live", session: await openBroadcast(token, ticket, self) });
    } catch (error) {
      setFlow({ step: "problem", problem: problemOf(error) });
    }
  }

  async function arrive(ticket: BroadcastTicket, name: string) {
    if (ticket.entry === "stage") return setFlow({ step: "lobby", ticket, name });
    if (ticket.entry === "wait") return setFlow({ step: "knocking", ticket, name });
    if (ticket.entry === "audience") return open(ticket, name);
    setFlow({ step: "outside", ticket });
  }

  async function request(name: string | null) {
    try {
      await arrive(await enterBroadcast(token, name), name ?? signedName);
    } catch (error) {
      setFlow({ step: "problem", problem: problemOf(error) });
    }
  }

  const begin = useEffectEvent(() => void request(null));
  useEffect(() => {
    if (flow.step !== "waiting" || session.status !== "signed-in" || started.current) return;
    started.current = true;
    begin();
  }, [flow.step, session.status]);

  const knock = useEffectEvent(async () => {
    if (flow.step !== "knocking") return;
    const ticket = await knockAgain(token, flow.ticket).catch(() => flow.ticket);
    if (ticket.entry !== "wait") void arrive(ticket, flow.name);
  });
  useEffect(() => {
    if (flow.step !== "knocking") return;
    const timer = window.setInterval(() => void knock(), KNOCK_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [flow.step]);

  return {
    flow: shownFlow(flow, session.status),
    join: (name: string) => {
      setFlow({ step: "joining" });
      void request(name);
    },
    enter: () => (flow.step === "lobby" ? void open(flow.ticket, flow.name) : undefined),
    retry: () => {
      started.current = false;
      setFlow({ step: "waiting" });
    },
  };
}
