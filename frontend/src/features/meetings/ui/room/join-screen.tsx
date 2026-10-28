import { useState } from "react";

import { useTranslations } from "use-intl";

import { ShosaiMark } from "@/components/shosai-mark";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

import type { LocalMedia } from "../../model/local-media";
import type { JoinFlow } from "../../model/use-join-flow";
import { CallMarks } from "./call-marks";
import { GuestNameForm } from "./guest-name-form";
import { SelfPreview } from "./self-preview";

type JoinPanelProps = Omit<JoinScreenProps, "media"> & { named: string; onNamed: (value: string) => void };

/** Правая часть лобби по шагу: имя гостя, готовая комната с отметками или ожидание сервера. */
function JoinPanel({ flow, named, onNamed, onName, onEnter }: JoinPanelProps) {
  const t = useTranslations("meetingRoom");
  if (flow.step === "name")
    return (
      <GuestNameForm
        value={named}
        onChange={onNamed}
        problem={flow.problem}
        pending={false}
        onSubmit={() => onName(named)}
      />
    );
  if (flow.step !== "lobby" && flow.step !== "entering")
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <span id="join-title" className="sr-only">
          {t("join.loading")}
        </span>
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-10 w-36" />
      </div>
    );
  const { room } = flow.joined;
  return (
    <>
      <div className="flex flex-col gap-2">
        <p className="text-muted-foreground text-sm">{t("join.ready")}</p>
        <h1 id="join-title" dir="auto" className="font-semibold text-2xl tracking-tight">
          {room.title ?? t("untitled")}
        </h1>
      </div>
      <CallMarks marks={{ notes: room.notes_on, recording: room.recording }} />
      {room.notes_on ? <p className="text-muted-foreground text-sm">{t("join.notesHint")}</p> : null}
      <Button size="lg" className="self-start" disabled={flow.step === "entering"} onClick={onEnter}>
        {flow.step === "entering" ? <Spinner data-icon="inline-start" /> : null}
        {t("join.enter")}
      </Button>
    </>
  );
}

type JoinScreenProps = {
  flow: Exclude<JoinFlow, { step: "call" } | { step: "problem" }>;
  media: LocalMedia;
  onName: (name: string) => void;
  onEnter: () => void;
};

/** Лобби: свой кадр и устройства; гость называет себя; перед входом видно, ведёт ли Leo заметки и идёт ли запись. */
export function JoinScreen({ flow, media, onName, onEnter }: JoinScreenProps) {
  const [named, setNamed] = useState("");
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="flex items-center px-4 py-3 sm:px-6">
        <ShosaiMark className="h-6" />
      </header>
      <main className="mx-auto grid w-full max-w-5xl flex-1 items-center gap-8 px-4 pb-12 sm:px-6 lg:grid-cols-[3fr_2fr]">
        <SelfPreview media={media} />
        <section aria-labelledby="join-title" className="flex flex-col gap-5">
          <JoinPanel flow={flow} named={named} onNamed={setNamed} onName={onName} onEnter={onEnter} />
        </section>
      </main>
    </div>
  );
}
