import { useEffect, useEffectEvent, useRef, useState } from "react";

import type { SessionStatus } from "@/features/identity/domain/session";
import { useSession } from "@/features/identity/model/session-store";
import { ApiError } from "@/lib/api/errors";

import { type JoinedRoom, roomApi } from "../api/room-api";
import type { CallSession } from "../domain/call-session";
import { type JoinProblem, joinProblemOf, retryable } from "../domain/join";
import { webDevice } from "../domain/web-device";
import type { LocalMedia } from "./local-media";
import { openCall } from "./open-call";

/* Путь от ссылки до звонка: имя гостя, вход на сервере, лобби с отметками, сам звонок (meetings §3.5). */

export type JoinFlow =
  | { step: "waiting" }
  | { step: "name"; problem: JoinProblem | null }
  | { step: "joining" }
  | { step: "lobby"; joined: JoinedRoom; name: string }
  | { step: "entering"; joined: JoinedRoom; name: string }
  | { step: "call"; session: CallSession }
  | { step: "problem"; problem: JoinProblem };

const problemOf = (error: unknown) =>
  error instanceof ApiError ? joinProblemOf(error.status, error.code) : joinProblemOf(0, null);

/** Шаг, который видит страница: пока сессия ждёт ответа, гость уже вводит имя, а вошедший — входит. */
function shownFlow(flow: JoinFlow, status: SessionStatus): JoinFlow {
  if (flow.step !== "waiting") return flow;
  if (status === "signed-out") return { step: "name", problem: null };
  return status === "signed-in" ? { step: "joining" } : flow;
}

export function useJoinFlow(token: string, media: LocalMedia) {
  const session = useSession();
  const [flow, setFlow] = useState<JoinFlow>({ step: "waiting" });
  // Вход вошедшего начинается один раз на попытку, в том числе при двойном запуске эффектов в разработке.
  const started = useRef(false);
  const signedName = session.me ? (session.me.display_name ?? session.me.full_name) : null;

  async function request(name: string | null) {
    try {
      const joined = await roomApi.join(token, name, webDevice(navigator.userAgent));
      setFlow({ step: "lobby", joined, name: name ?? signedName ?? "" });
    } catch (error) {
      const problem = problemOf(error);
      // Гость остаётся у своего имени, когда стоит попробовать ещё раз; окончательный отказ — на всю страницу.
      setFlow(name !== null && retryable(problem) ? { step: "name", problem } : { step: "problem", problem });
    }
  }

  const begin = useEffectEvent(() => void request(null));
  useEffect(() => {
    if (flow.step !== "waiting" || session.status !== "signed-in" || started.current) return;
    started.current = true;
    begin();
  }, [flow.step, session.status]);

  async function enter() {
    if (flow.step !== "lobby") return;
    const { joined, name } = flow;
    setFlow({ step: "entering", joined, name });
    try {
      const call = await openCall({
        token,
        identity: joined.identity,
        name,
        role: joined.role,
        title: joined.room.title,
        marks: { notes: joined.room.notes_on, recording: joined.room.recording },
        link: `${window.location.origin}/meet/${token}`,
        livekit: { url: joined.livekit_url, token: joined.livekit_token },
        media: { mic: media.mic, camera: media.camera, stream: media.stream },
      });
      setFlow({ step: "call", session: call });
    } catch (error) {
      setFlow({ step: "problem", problem: problemOf(error) });
    }
  }

  return {
    flow: shownFlow(flow, session.status),
    join: (name: string) => {
      setFlow({ step: "joining" });
      void request(name);
    },
    enter,
    retry: () => {
      started.current = false;
      setFlow({ step: "waiting" });
    },
  };
}
