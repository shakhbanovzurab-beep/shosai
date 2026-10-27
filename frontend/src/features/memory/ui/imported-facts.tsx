"use client";

import { useState } from "react";

import { LoadError } from "@/components/feedback";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ItemGroup } from "@/components/ui/item";
import { Skeleton } from "@/components/ui/skeleton";

import type { MemoryWords } from "../model/fact-actions";
import { answerImported, importedResource, moreImported, turnDownImported, useImported } from "../model/imported";
import { CandidateRow } from "./candidate-row";

/** «Не запоминать их» — все перенесённые разом, поэтому после подтверждения. */
function TurnDownAll({ words }: { words: MemoryWords }) {
  const { t, common } = words;
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="sm" className="self-start text-destructive">
          {t("imported.turnDown")}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("imported.confirmTitle")}</AlertDialogTitle>
          <AlertDialogDescription>{t("imported.confirmDescription")}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={() => void turnDownImported(words)}>
            {t("imported.turnDown")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ImportedList({ words }: { words: MemoryWords }) {
  const { t } = words;
  const state = useImported();
  if (state.status === "loading") return <Skeleton className="h-24 rounded-xl" />;
  if (state.status === "error")
    return (
      <LoadError title={t("failed.load")} message={state.message} onRetry={() => void importedResource.refresh()} />
    );
  const page = state.data;
  return (
    <div className="flex flex-col gap-3">
      <ItemGroup>
        {page.items.map((fact) => (
          <CandidateRow
            key={fact.id}
            fact={fact}
            words={words}
            onAnswer={(remember) => void answerImported(fact, remember, words)}
          />
        ))}
      </ItemGroup>
      {page.next_cursor === null ? null : (
        <Button variant="ghost" size="sm" className="self-center" onClick={() => void moreImported()}>
          {t("more")}
        </Button>
      )}
      {page.items.length > 0 ? <TurnDownAll words={words} /> : null}
    </div>
  );
}

/** Перенесённые из прежней памяти (MM-D8): своим списком, без ежедневного «Запомнить это?»; разбор — по желанию. */
export function ImportedFacts({ count, words }: { count: number; words: MemoryWords }) {
  const { t } = words;
  const [open, setOpen] = useState(false);
  if (count === 0) return null;
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {t("imported.title")}
          <Badge variant="secondary" className="tabular-nums">
            {count}
          </Badge>
        </CardTitle>
        <CardDescription>{t("imported.description")}</CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" aria-expanded={open} onClick={() => setOpen((shown) => !shown)}>
            {open ? t("imported.hide") : t("imported.review")}
          </Button>
        </CardAction>
      </CardHeader>
      {open ? (
        <CardContent>
          <ImportedList words={words} />
        </CardContent>
      ) : null}
    </Card>
  );
}
