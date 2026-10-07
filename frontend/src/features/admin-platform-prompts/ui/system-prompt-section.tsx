"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";

import { PLACEHOLDERS, SYSTEM_PROMPT_MAX } from "../domain/contract";
import { fillExamples } from "../domain/format";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { PromptField } from "./prompt-field";

/** What every request is built from, in order; the platform layer is this screen. */
function AssemblyPreview({ systemPrompt }: { systemPrompt: string }) {
  const layers = [
    {
      title: "1. Платформа",
      note: "Этот промт + промт активной функции + включённые правила безопасности",
      content: systemPrompt.trim() ? fillExamples(systemPrompt) : "(пусто — платформенный слой не отправляется)",
      current: true,
    },
    {
      title: "2. Пользовательский контекст из Studio",
      note: "Личный контекст и промт роли, если пользователю разрешено их менять",
      content: "<контекст пользователя>",
      current: false,
    },
    { title: "3. Сообщение", note: "Вопрос пользователя в чате или голосом", content: "<сообщение>", current: false },
  ];

  return (
    <Card className="h-fit shadow-xs">
      <CardHeader>
        <CardTitle>Как собирается запрос</CardTitle>
        <CardDescription>Переменные показаны с примерами значений.</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-2">
          {layers.map((layer) => (
            <li
              key={layer.title}
              className={
                layer.current
                  ? "rounded-lg border border-primary/40 bg-primary/5 p-3"
                  : "rounded-lg border bg-muted/40 p-3"
              }
            >
              <p className="font-medium text-xs">{layer.title}</p>
              <p className="text-muted-foreground text-xs">{layer.note}</p>
              <p className="mt-1.5 line-clamp-6 whitespace-pre-wrap break-words font-mono text-xs leading-5">
                {layer.content}
              </p>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function PlaceholdersHelp() {
  return (
    <Card className="h-fit shadow-xs">
      <CardHeader>
        <CardTitle>Переменные</CardTitle>
        <CardDescription>Заполняются для каждого пользователя перед отправкой.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-col gap-2 text-xs">
          {PLACEHOLDERS.map((placeholder) => (
            <div key={placeholder.key} className="flex flex-col gap-0.5">
              <dt>
                <code className="rounded bg-muted px-1 py-0.5 font-mono">{`{{${placeholder.key}}}`}</code>
              </dt>
              <dd className="text-muted-foreground">
                {placeholder.description} · например, «{placeholder.example}»
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

/** The global system prompt every Leo conversation starts with. */
export function SystemPromptSection() {
  const {
    state: { config },
    actions: { update },
  } = usePlatformPrompts();

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <Card className="shadow-xs">
        <CardHeader>
          <CardTitle>
            <Label htmlFor="platform-system-prompt">Глобальный системный промт Leo</Label>
          </CardTitle>
          <CardDescription>
            Открывает каждый разговор у всех пользователей — в чате, голосовом режиме и агентских действиях. Пишите
            правила, которые не зависят от конкретного человека.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PromptField
            id="platform-system-prompt"
            label="Глобальный системный промт Leo"
            value={config.system_prompt}
            onChange={(system_prompt) => update((current) => ({ ...current, system_prompt }))}
            maxChars={SYSTEM_PROMPT_MAX}
            placeholder="Ты — Leo, ИИ-ассистент…"
            className="min-h-96"
          />
        </CardContent>
      </Card>
      <div className="flex flex-col gap-4">
        <AssemblyPreview systemPrompt={config.system_prompt} />
        <PlaceholdersHelp />
      </div>
    </div>
  );
}
