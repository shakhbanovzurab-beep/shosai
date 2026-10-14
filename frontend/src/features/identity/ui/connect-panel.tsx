import { useState, useTransition } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Link } from "@/lib/navigation";

import type { DesktopRequest } from "../domain/desktop-link";
import { HOME_PATH } from "../domain/next-path";
import { connectDesktop } from "../model/desktop-connect";
import type { Refusal } from "../model/outcome";
import { useMe } from "../model/session-store";
import { AuthHeading } from "./auth-heading";
import { ProblemMessage } from "./problem-message";

/**
 * Подключение десктоп-приложения: человек видит, каким аккаунтом войдёт приложение, и подтверждает. Без
 * подтверждения код не выдаётся — чужое приложение не получит сессию тихо.
 */
export function ConnectPanel({ request }: { request: DesktopRequest | null }) {
  const t = useTranslations("identityDesktop");
  const me = useMe();
  const [connected, setConnected] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [pending, startTransition] = useTransition();

  if (request === null) {
    return <AuthHeading title={t("invalidTitle")}>{t("invalid")}</AuthHeading>;
  }

  const connect = () => {
    startTransition(async () => {
      const outcome = await connectDesktop(request);
      setConnected(outcome.kind === "done");
      setRefusal(outcome.kind === "done" ? null : outcome);
    });
  };

  if (connected) {
    return (
      <>
        <AuthHeading title={t("doneTitle")}>{t("done")}</AuthHeading>
        <Button variant="outline" size="lg" disabled={pending} onClick={connect}>
          {t("openAgain")}
        </Button>
      </>
    );
  }
  return (
    <>
      <AuthHeading title={t("title")}>{t("description", { email: me?.email ?? "" })}</AuthHeading>
      <div className="flex flex-col gap-3">
        {refusal === null ? null : <ProblemMessage refusal={refusal} />}
        <Button size="lg" disabled={pending} onClick={connect}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {pending ? t("opening") : t("submit")}
        </Button>
        <Button variant="ghost" size="lg" asChild>
          <Link href={HOME_PATH}>{t("cancel")}</Link>
        </Button>
      </div>
    </>
  );
}
