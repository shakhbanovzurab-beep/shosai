"use client";

import { type FormEvent, useState } from "react";

import { X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

import { TOPIC_MAX, TOPICS_LIMIT } from "../domain/contract";
import { useSafety } from "../model/use-safety";
import { NotEnglishHint } from "./not-english-hint";

export function BlockedTopicsCard() {
  const { safety, set } = useSafety();
  const [text, setText] = useState("");
  const value = text.trim();
  const duplicate = safety.blocked_topics.some((topic) => topic.toLowerCase() === value.toLowerCase());
  const full = safety.blocked_topics.length >= TOPICS_LIMIT;

  const add = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!value || duplicate || full) return;
    set((current) => ({ blocked_topics: [...current.blocked_topics, value] }));
    setText("");
  };

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>Запрещённые темы</CardTitle>
        <CardDescription>
          Leo вежливо отказывается их обсуждать и не ищет по ним в сети. Темы пишутся по-английски.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {safety.blocked_topics.length === 0 ? (
          <p className="text-muted-foreground text-sm">Ограничений по темам нет.</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5" aria-label="Запрещённые темы">
            {safety.blocked_topics.map((topic) => (
              <li key={topic}>
                <Badge variant="secondary" className="h-auto gap-1 whitespace-normal py-0.5 pr-0.5">
                  {topic}
                  <button
                    type="button"
                    onClick={() =>
                      set((current) => ({ blocked_topics: current.blocked_topics.filter((item) => item !== topic) }))
                    }
                    aria-label={`Убрать тему «${topic}»`}
                    className="rounded-full p-0.5 hover:bg-foreground/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <X className="size-3" aria-hidden="true" />
                  </button>
                </Badge>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={add} className="flex gap-2">
          <Input
            value={text}
            onChange={(event) => setText(event.currentTarget.value)}
            maxLength={TOPIC_MAX}
            placeholder="For example: gambling and casinos"
            aria-label="Новая запрещённая тема"
            aria-invalid={duplicate}
            lang="en"
            disabled={full}
          />
          <Button type="submit" variant="outline" disabled={!value || duplicate || full} className="shrink-0">
            Добавить
          </Button>
        </form>
        {duplicate ? <p className="text-destructive text-xs">Такая тема уже есть.</p> : null}
        <NotEnglishHint text={safety.blocked_topics.join(" ")} />
      </CardContent>
    </Card>
  );
}
