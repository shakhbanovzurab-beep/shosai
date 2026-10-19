"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

import { forgetAll, type MemoryWords } from "../model/fact-actions";

/** «Забыть всё» — необратимо, поэтому только после подтверждения. */
export function ForgetAll({ count, words }: { count: number; words: MemoryWords }) {
  const { t, common } = words;
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="sm" className="text-destructive">
          {t("forgetAll.button")}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("forgetAll.title")}</AlertDialogTitle>
          <AlertDialogDescription>{t("forgetAll.description", { count })}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={() => void forgetAll(words)}>
            {t("forgetAll.confirm")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
