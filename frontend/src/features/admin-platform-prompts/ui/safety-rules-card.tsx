"use client";

import { type FormEvent, useState } from "react";

import { ArrowDown, ArrowUp, Plus, ShieldCheck, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

import { type GuardrailRule, RULE_MAX, RULES_LIMIT } from "../domain/contract";
import { useSafety } from "../model/use-safety";
import { NotEnglishHint } from "./not-english-hint";

function moved<T>(items: T[], from: number, to: number) {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function RuleRow({ rule, index, count }: { rule: GuardrailRule; index: number; count: number }) {
  const { set } = useSafety();
  const number = index + 1;
  const change = (patch: Partial<GuardrailRule>) =>
    set((safety) => ({ rules: safety.rules.map((item) => (item.id === rule.id ? { ...item, ...patch } : item)) }));
  const move = (to: number) => set((safety) => ({ rules: moved(safety.rules, index, to) }));
  const empty = rule.text.trim().length === 0;

  return (
    <li className="flex items-start gap-2 rounded-lg border bg-card p-2" data-disabled={!rule.enabled || undefined}>
      <span className="mt-2 w-6 shrink-0 text-center font-mono text-muted-foreground text-xs tabular-nums">
        {number}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <Input
          value={rule.text}
          onChange={(event) => change({ text: event.currentTarget.value })}
          maxLength={RULE_MAX}
          aria-label={`Правило ${number}`}
          aria-invalid={empty}
          lang="en"
          className={rule.enabled ? undefined : "text-muted-foreground line-through"}
        />
        {empty ? <p className="text-destructive text-xs">Пустое правило не будет опубликовано.</p> : null}
        {rule.enabled ? <NotEnglishHint text={rule.text} /> : null}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Switch
          checked={rule.enabled}
          onCheckedChange={(enabled) => change({ enabled })}
          aria-label={`Правило ${number} включено`}
          className="mx-1"
        />
        <Button
          variant="ghost"
          size="icon-sm"
          disabled={index === 0}
          onClick={() => move(index - 1)}
          aria-label={`Поднять правило ${number}`}
        >
          <ArrowUp />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          disabled={index === count - 1}
          onClick={() => move(index + 1)}
          aria-label={`Опустить правило ${number}`}
        >
          <ArrowDown />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => set((safety) => ({ rules: safety.rules.filter((item) => item.id !== rule.id) }))}
          aria-label={`Удалить правило ${number}`}
        >
          <Trash2 />
        </Button>
      </div>
    </li>
  );
}

export function RulesCard() {
  const { safety, set } = useSafety();
  const [text, setText] = useState("");
  const full = safety.rules.length >= RULES_LIMIT;

  const add = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = text.trim();
    if (!value || full) return;
    set((current) => ({ rules: [...current.rules, { id: crypto.randomUUID(), text: value, enabled: true }] }));
    setText("");
  };

  return (
    <Card className="shadow-xs lg:col-span-2">
      <CardHeader>
        <CardTitle>Правила</CardTitle>
        <CardDescription>
          Идут после системного промта сверху вниз, по-английски. Выключенные правила хранятся, но не отправляются.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {safety.rules.length === 0 ? (
          <Empty className="border border-dashed py-6">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <ShieldCheck />
              </EmptyMedia>
              <EmptyTitle>Правил пока нет</EmptyTitle>
              <EmptyDescription>Добавьте первое правило — например, что Leo не должен делать.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ol className="flex flex-col gap-2" aria-label="Правила безопасности">
            {safety.rules.map((rule, index) => (
              <RuleRow key={rule.id} rule={rule} index={index} count={safety.rules.length} />
            ))}
          </ol>
        )}
        <form onSubmit={add} className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={text}
            onChange={(event) => setText(event.currentTarget.value)}
            maxLength={RULE_MAX}
            placeholder="For example: Never promise delivery dates on the company's behalf."
            aria-label="Текст нового правила"
            lang="en"
            disabled={full}
          />
          <Button type="submit" variant="outline" disabled={full || !text.trim()} className="shrink-0">
            <Plus data-icon="inline-start" />
            Добавить правило
          </Button>
        </form>
        {full ? <p className="text-muted-foreground text-xs">Достигнут лимит — {RULES_LIMIT} правил.</p> : null}
      </CardContent>
    </Card>
  );
}
