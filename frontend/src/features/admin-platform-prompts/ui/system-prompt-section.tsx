"use client";

import { cn } from "cn";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";

import { LAYER_TOKENS, type PlatformConfig, SYSTEM_PROMPT_MAX } from "../domain/contract";
import { formatNumber } from "../domain/format";
import { cleaned, estimateTokens, layerText } from "../domain/platform-layer";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { PromptField } from "./prompt-field";

const LAYERS = [
  {
    title: "1. Политика Leo",
    note: "Задана в коде и не меняется отсюда: подтверждение действий, язык ответа, безопасность.",
  },
  { title: "2. Слой платформы — этот экран", note: "Системный промт, включённые правила и запрещённые темы." },
  { title: "3. Профиль и личный контекст из Studio", note: "Имя, часовой пояс, язык, контекст и промт роли." },
  { title: "4. Сообщение", note: "Вопрос в чате или голосом." },
] as const;

/** Из чего собирается запрос Leo по порядку и сколько из бюджета занимает слой платформы. */
function AssemblyPreview({ config }: { config: PlatformConfig }) {
  const text = layerText(cleaned(config));
  const tokens = estimateTokens(text);
  const over = tokens > LAYER_TOKENS;

  return (
    <Card className="h-fit shadow-xs">
      <CardHeader>
        <CardTitle>Как собирается запрос</CardTitle>
        <CardDescription>Слой доходит до Leo в чате и голосом и до ответов десктопа.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ol className="flex flex-col gap-2">
          {LAYERS.map((layer, index) => (
            <li
              key={layer.title}
              className={cn("rounded-lg border p-3", index === 1 ? "border-primary/40 bg-primary/5" : "bg-muted/40")}
            >
              <p className="font-medium text-xs">{layer.title}</p>
              <p className="text-muted-foreground text-xs">{layer.note}</p>
              {index === 1 ? (
                <p className="mt-1.5 line-clamp-6 whitespace-pre-wrap break-words font-mono text-xs leading-5">
                  {text || "(пусто — слой платформы не отправляется)"}
                </p>
              ) : null}
            </li>
          ))}
        </ol>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-xs">
            <span>Бюджет слоя</span>
            <span className={cn("tabular-nums", over ? "text-destructive" : "text-muted-foreground")}>
              ≈{formatNumber(tokens)} из {formatNumber(LAYER_TOKENS)} токенов
            </span>
          </div>
          <Progress
            value={Math.min(100, (tokens / LAYER_TOKENS) * 100)}
            aria-label="Бюджет слоя платформы"
            className={over ? "*:data-[slot=progress-indicator]:bg-destructive" : undefined}
          />
        </div>
      </CardContent>
    </Card>
  );
}

/** Системный промт слоя платформы — общий для всех пользователей. */
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
            <Label htmlFor="platform-system-prompt">Системный промт платформы</Label>
          </CardTitle>
          <CardDescription>
            Идёт сразу после политики Leo во всех разговорах. Пишите по-английски правила, которые не зависят от
            конкретного человека: имя, время и язык Leo знает сам.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PromptField
            id="platform-system-prompt"
            label="Системный промт платформы"
            value={config.system_prompt}
            onChange={(system_prompt) => update((current) => ({ ...current, system_prompt }))}
            maxChars={SYSTEM_PROMPT_MAX}
            placeholder="For example: Keep answers short and name the source of every fact."
            className="min-h-96"
          />
        </CardContent>
      </Card>
      <AssemblyPreview config={config} />
    </div>
  );
}
