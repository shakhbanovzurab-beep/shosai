"use client";

import { useTransition } from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { apiErrorDescription } from "@/lib/api/error-description";

import type { LibraryFolder } from "../domain/library";
import { loadMore } from "../model/library-resource";

/** Кнопка под библиотекой: следующие, более ранние встречи; пока они едут, кнопка ждёт. */
export function LoadMore({ folder }: { readonly folder: LibraryFolder | undefined }) {
  const t = useTranslations("notes");
  const [loading, startLoading] = useTransition();
  const more = () =>
    startLoading(async () => {
      try {
        await loadMore(folder);
      } catch (error) {
        toast.error(t("library.moreFailed"), { description: apiErrorDescription(error) });
      }
    });
  return (
    <Button variant="outline" className="self-center" disabled={loading} onClick={more}>
      {loading ? <Spinner data-icon="inline-start" /> : null}
      {t("library.more")}
    </Button>
  );
}
