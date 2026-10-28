import { useState } from "react";

import type { BroadcastSession } from "../../domain/broadcast";
import { useBroadcastFlow } from "../../model/broadcast-flow";
import { useBroadcastSnapshot } from "../../model/broadcast-session";
import { useLocalMedia } from "../../model/local-media";
import { RoomProblem } from "../room/room-problem";
import { BroadcastOutside } from "./broadcast-outside";
import { BroadcastArrival, StudioLobby } from "./studio-lobby";
import { StudioScreen } from "./studio-screen";
import { WatchScreen } from "./watch-screen";

type LiveBroadcastProps = { session: BroadcastSession; token: string; onRejoin: () => void };

/** Идущая трансляция: сцене — студия, залу — эфир; позванный на сцену зритель переходит в студию. */
function LiveBroadcast({ session, token, onRejoin }: LiveBroadcastProps) {
  const broadcast = useBroadcastSnapshot(session);
  const [left, setLeft] = useState(false);
  if (left) return <BroadcastOutside kind="left" onRetry={onRejoin} />;
  if (broadcast.status === "ended") return <BroadcastOutside kind="ended" onRetry={null} />;
  if (broadcast.role)
    return (
      <StudioScreen session={session} link={`${window.location.origin}/live/${token}`} onLeft={() => setLeft(true)} />
    );
  return <WatchScreen session={session} onLeft={() => setLeft(true)} />;
}

/** Страница трансляции по ссылке `/app/live/{token}`: имя гостя, лобби сцены, студия или эфир, или почему не войти. */
export function BroadcastScreen({ token }: { token: string }) {
  const media = useLocalMedia();
  const { flow, join, enter, retry } = useBroadcastFlow(token, media);
  if (flow.step === "live") return <LiveBroadcast session={flow.session} token={token} onRejoin={retry} />;
  if (flow.step === "lobby") return <StudioLobby ticket={flow.ticket} media={media} onEnter={enter} />;
  if (flow.step === "knocking") return <BroadcastOutside kind="wait" onRetry={null} />;
  if (flow.step === "outside") {
    const { entry } = flow.ticket;
    const kind = entry === "not_live" || entry === "full" ? entry : "ended";
    return <BroadcastOutside kind={kind} onRetry={retry} />;
  }
  if (flow.step === "problem") return <RoomProblem problem={flow.problem} onRetry={retry} />;
  return <BroadcastArrival naming={flow.step === "name"} onName={join} />;
}
