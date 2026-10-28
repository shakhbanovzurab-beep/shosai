import { useState } from "react";

import { useTranslations } from "use-intl";

import { ShosaiMark } from "@/components/shosai-mark";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

import type { BroadcastTicket } from "../../domain/broadcast";
import type { LocalMedia } from "../../model/local-media";
import { GuestNameForm } from "../room/guest-name-form";
import { SelfPreview } from "../room/self-preview";

type StudioLobbyProps = { ticket: BroadcastTicket; media: LocalMedia; onEnter: () => void };

/** Лобби сцены: свой кадр и устройства, роль и название; эфир зал увидит, только когда ведущий его начнёт. */
export function StudioLobby({ ticket, media, onEnter }: StudioLobbyProps) {
  const t = useTranslations("meetingBroadcast");
  const [entering, setEntering] = useState(false);
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="flex items-center px-4 py-3 sm:px-6">
        <ShosaiMark className="h-6" />
      </header>
      <main className="mx-auto grid w-full max-w-5xl flex-1 items-center gap-8 px-4 pb-12 sm:px-6 lg:grid-cols-[3fr_2fr]">
        <SelfPreview media={media} />
        <section aria-labelledby="studio-title" className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <p className="text-muted-foreground text-sm">
              {t("lobby.ready", { role: t(`roles.${ticket.role ?? "speaker"}`) })}
            </p>
            <h1 id="studio-title" dir="auto" className="font-semibold text-2xl tracking-tight">
              {ticket.title}
            </h1>
          </div>
          <p className="text-muted-foreground text-sm">{t("lobby.hint")}</p>
          <Button
            size="lg"
            className="self-start"
            disabled={entering}
            onClick={() => {
              setEntering(true);
              onEnter();
            }}
          >
            {entering ? <Spinner data-icon="inline-start" /> : null}
            {t("lobby.enter")}
          </Button>
        </section>
      </main>
    </div>
  );
}

/** Гость называет себя, прежде чем ссылка ответит; пока ответа нет — заглушка. */
export function BroadcastArrival({ naming, onName }: { naming: boolean; onName: (name: string) => void }) {
  const [named, setNamed] = useState("");
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="flex items-center px-4 py-3 sm:px-6">
        <ShosaiMark className="h-6" />
      </header>
      <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-5 px-4 pb-12">
        {naming ? (
          <GuestNameForm
            value={named}
            onChange={setNamed}
            problem={null}
            pending={false}
            onSubmit={() => onName(named)}
          />
        ) : (
          <div className="flex flex-col gap-3" aria-busy="true">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-10 w-36" />
          </div>
        )}
      </main>
    </div>
  );
}
