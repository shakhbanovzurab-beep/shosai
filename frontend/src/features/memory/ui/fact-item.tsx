"use client";

import { useEffect, useId, useRef, useState } from "react";

import { Pencil, Pin, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Item, ItemActions, ItemContent, ItemDescription, ItemTitle } from "@/components/ui/item";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

import { type MemoryFact, STATEMENT_MAX } from "../domain/contract";
import { type MemoryWords, saveFactEdit, setPinned } from "../model/fact-actions";
import { forgetFact } from "../model/pending-forget";
import { FactMeta } from "./fact-meta";

type FactEditorProps = {
  fact: MemoryFact;
  /** Черновик начинается с этого текста и дальше живёт сам; редактор открывается заново на каждую правку. */
  initialStatement: string;
  words: MemoryWords;
  onDone: () => void;
};

/** Правка текста на месте: Enter сохраняет, Shift+Enter — новая строка. */
function FactEditor({ fact, initialStatement, words, onDone }: FactEditorProps) {
  const { t, common } = words;
  const [text, setText] = useState(initialStatement);
  const [saving, setSaving] = useState(false);
  const field = useRef<HTMLTextAreaElement>(null);
  useEffect(() => field.current?.focus(), []);

  const save = async () => {
    const statement = text.trim();
    if (statement === "" || statement === initialStatement) return onDone();
    if (await saveFactEdit(fact, statement, words, setSaving)) onDone();
  };

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <Textarea
        ref={field}
        value={text}
        rows={2}
        dir="auto"
        maxLength={STATEMENT_MAX}
        aria-label={t("editLabel")}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Enter" || event.shiftKey) return;
          event.preventDefault();
          void save();
        }}
      />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? <Spinner data-icon="inline-start" /> : null}
          {common("actions.save")}
        </Button>
      </div>
    </form>
  );
}

/** Факт, который Leo использует: текст, источник, закрепление; править и забыть — по наведению или фокусу. */
export function FactItem({ fact, words }: { fact: MemoryFact; words: MemoryWords }) {
  const { t } = words;
  const [editing, setEditing] = useState(false);
  const statementId = useId();

  return (
    <Item role="listitem" size="sm" className="flex-nowrap items-start">
      <ItemContent className="min-w-0">
        {editing ? (
          <FactEditor fact={fact} initialStatement={fact.statement} words={words} onDone={() => setEditing(false)} />
        ) : (
          <ItemTitle id={statementId} dir="auto" className="line-clamp-none font-normal">
            {fact.statement}
          </ItemTitle>
        )}
        <ItemDescription className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          <FactMeta fact={fact} />
          {fact.pinned ? <Badge variant="secondary">{t("pinned")}</Badge> : null}
        </ItemDescription>
      </ItemContent>
      {editing ? null : (
        // С мышью действия появляются по наведению или фокусу; на сенсорном экране видны всегда.
        <ItemActions className="gap-0.5 pointer-fine:opacity-0 pointer-fine:group-focus-within/item:opacity-100 pointer-fine:group-hover/item:opacity-100">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("actions.pin")}
            aria-pressed={fact.pinned}
            aria-describedby={statementId}
            onClick={() => void setPinned(fact, !fact.pinned, words)}
          >
            <Pin className={fact.pinned ? "fill-current" : undefined} />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("actions.edit")}
            aria-describedby={statementId}
            onClick={() => setEditing(true)}
          >
            <Pencil />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("actions.forget")}
            aria-describedby={statementId}
            onClick={() => void forgetFact(fact, words)}
          >
            <Trash2 />
          </Button>
        </ItemActions>
      )}
    </Item>
  );
}
