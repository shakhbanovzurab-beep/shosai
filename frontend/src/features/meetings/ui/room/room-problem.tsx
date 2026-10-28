import type { LucideIcon } from "lucide-react";
import { Ban, CircleSlash, DoorOpen, PhoneOff, RefreshCw, Users, VideoOff, WifiOff } from "lucide-react";
import { useTranslations } from "use-intl";

import { ShosaiMark } from "@/components/shosai-mark";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { useSession } from "@/features/identity/model/session-store";
import { Link } from "@/lib/navigation";

import { type CallEnd, type JoinProblem, retryable } from "../../domain/join";

const PROBLEM_ICONS: Record<JoinProblem, LucideIcon> = {
  not_found: CircleSlash,
  room_finished: PhoneOff,
  removed: Ban,
  room_full: Users,
  video_unavailable: VideoOff,
  rate_limited: RefreshCw,
  unknown: WifiOff,
};

const END_ICONS: Record<CallEnd, LucideIcon> = { left: DoorOpen, ended: PhoneOff, removed: Ban, lost: WifiOff };

type RoomStateProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  action: { label: string; run: () => void } | null;
};

/** Страница вместо звонка: что случилось и что можно сделать; вошедший человек возвращается во «Встречи». */
function RoomState({ icon: Icon, title, description, action }: RoomStateProps) {
  const t = useTranslations("meetingRoom");
  const signedIn = useSession().status === "signed-in";
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="flex items-center px-4 py-3 sm:px-6">
        <ShosaiMark className="h-6" />
      </header>
      <main className="flex flex-1 items-center justify-center px-4 pb-12">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Icon aria-hidden="true" />
            </EmptyMedia>
            <EmptyTitle>
              <h1>{title}</h1>
            </EmptyTitle>
            <EmptyDescription>{description}</EmptyDescription>
          </EmptyHeader>
          <EmptyContent className="flex-row justify-center">
            {action ? <Button onClick={action.run}>{action.label}</Button> : null}
            {signedIn ? (
              <Button asChild variant="outline">
                <Link href="/app/meetings">{t("states.toMeetings")}</Link>
              </Button>
            ) : null}
          </EmptyContent>
        </Empty>
      </main>
    </div>
  );
}

/** Почему в звонок не войти: конец встречи, удаление, нет мест, сервер видео недоступен. */
export function RoomProblem({ problem, onRetry }: { problem: JoinProblem; onRetry: () => void }) {
  const t = useTranslations("meetingRoom");
  return (
    <RoomState
      icon={PROBLEM_ICONS[problem]}
      title={t(`problems.${problem}.title`)}
      description={t(`problems.${problem}.description`)}
      action={retryable(problem) ? { label: t("states.retry"), run: onRetry } : null}
    />
  );
}

/** Звонок закончился у этого участника: вышел сам, встречу завершили, удалили или пропала связь. */
export function CallEnded({ end, onRejoin }: { end: CallEnd; onRejoin: () => void }) {
  const t = useTranslations("meetingRoom");
  const rejoin = end === "left" || end === "lost";
  return (
    <RoomState
      icon={END_ICONS[end]}
      title={t(`ends.${end}.title`)}
      description={t(`ends.${end}.description`)}
      action={rejoin ? { label: t("states.rejoin"), run: onRejoin } : null}
    />
  );
}
