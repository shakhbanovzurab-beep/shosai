"use client";

import { useTransition } from "react";

import { RotateCcw } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRouter } from "@/lib/navigation";

/** Reads the downloads again: the page is server-rendered, so a refresh re-runs the read. */
export function RetryButton() {
  const t = useTranslations("common");
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <Button
      variant="outline"
      size="sm"
      className="w-fit"
      disabled={pending}
      onClick={() => startTransition(() => router.refresh())}
    >
      {pending ? <Spinner data-icon="inline-start" /> : <RotateCcw data-icon="inline-start" />}
      {t("actions.retry")}
    </Button>
  );
}
