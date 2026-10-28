import { useLocalMedia } from "../../model/local-media";
import { useJoinFlow } from "../../model/use-join-flow";
import { CallScreen } from "./call-screen";
import { JoinScreen } from "./join-screen";
import { RoomProblem } from "./room-problem";

/** Страница комнаты по ссылке: лобби, звонок или объяснение, почему не войти. Свои устройства живут всю страницу. */
export function RoomScreen({ token }: { token: string }) {
  const media = useLocalMedia();
  const { flow, join, enter, retry } = useJoinFlow(token, media);
  if (flow.step === "call") return <CallScreen session={flow.session} media={media} onRejoin={retry} />;
  if (flow.step === "problem") return <RoomProblem problem={flow.problem} onRetry={retry} />;
  return <JoinScreen flow={flow} media={media} onName={(name) => void join(name)} onEnter={() => void enter()} />;
}
