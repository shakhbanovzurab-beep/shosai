"use client";

import { useState } from "react";

import { CircleCheck, KeyRound, PlugZap, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";

import type { ConnectionCheckResponse, OpenRouterCredits, ProviderStatus } from "../domain/contract";
import { formatTime, formatUsd } from "../domain/format";
import { SOURCE_LABEL } from "../domain/labels";
import { checkConnection } from "../model/ai-models-store";

export function ProviderCard({ provider }: { provider: ProviderStatus }) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="font-normal">OpenRouter</CardTitle>
        <CardDescription>Единый провайдер OpenRouter по серверному ключу.</CardDescription>
        <CardAction>
          <KeyStatusBadge configured={provider.key_configured} />
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-4">
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Ключ</dt>
          <dd className="flex min-w-0 items-center gap-1.5">
            <KeyRound className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span className="truncate font-mono text-xs">
              OPENROUTER_API_KEY{provider.key_hint ? ` ${provider.key_hint}` : ""}
            </span>
          </dd>
          <dt className="text-muted-foreground">Источник</dt>
          <dd className="truncate">{SOURCE_LABEL[provider.source]}</dd>
        </dl>

        <CreditsBalance credits={provider.credits} keyConfigured={provider.key_configured} />

        {provider.sync_error ? (
          <p className="flex items-start gap-1.5 text-destructive text-sm" role="alert">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {provider.sync_error}
          </p>
        ) : null}
      </CardContent>

      <CardFooter>
        <ConnectionCheck />
      </CardFooter>
    </Card>
  );
}

function KeyStatusBadge({ configured }: { configured: boolean }) {
  return configured ? (
    <Badge className="bg-green-500/10 text-green-700 dark:bg-green-500/15 dark:text-green-300">
      <CircleCheck aria-hidden="true" />
      Ключ настроен
    </Badge>
  ) : (
    <Badge variant="destructive">
      <TriangleAlert aria-hidden="true" />
      Ключ не задан
    </Badge>
  );
}

function CreditsBalance({ credits, keyConfigured }: { credits: OpenRouterCredits | null; keyConfigured: boolean }) {
  if (!credits)
    return (
      <div className="flex flex-col gap-2">
        <span className="text-muted-foreground text-sm">Баланс кредитов</span>
        <p className="text-muted-foreground text-sm">
          {keyConfigured
            ? "OpenRouter не сообщил баланс."
            : "Задайте переменную окружения OPENROUTER_API_KEY на сервере, чтобы видеть баланс и актуальные цены."}
        </p>
      </div>
    );

  const usedShare = credits.total > 0 ? Math.min(100, (credits.used / credits.total) * 100) : 0;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-muted-foreground text-sm">Баланс кредитов</span>
        <span className="text-muted-foreground text-xs tabular-nums">из {formatUsd(credits.total)}</span>
      </div>
      <div className="text-2xl tabular-nums leading-none tracking-tight">{formatUsd(credits.remaining)}</div>
      <Progress value={usedShare} aria-label="Израсходовано кредитов" />
      <span className="text-muted-foreground text-xs tabular-nums">Израсходовано {formatUsd(credits.used)}</span>
    </div>
  );
}

function describeCheck(check: ConnectionCheckResponse) {
  const parts = [check.ok ? "Работает" : "Ошибка", formatTime(check.checked_at)];
  if (check.ok && check.latency_ms !== null) parts.push(`${check.latency_ms} мс`);
  return parts.join(" · ");
}

function ConnectionCheck() {
  const [checking, setChecking] = useState(false);
  const [lastCheck, setLastCheck] = useState<ConnectionCheckResponse | null>(null);

  async function runCheck() {
    setChecking(true);
    setLastCheck(await checkConnection());
    setChecking(false);
  }

  return (
    <div className="flex w-full flex-wrap items-center justify-between gap-2">
      <Button variant="outline" size="sm" onClick={runCheck} disabled={checking}>
        {checking ? <Spinner /> : <PlugZap aria-hidden="true" />}
        Проверить подключение
      </Button>
      <p className="text-muted-foreground text-xs tabular-nums" aria-live="polite">
        {lastCheck ? describeCheck(lastCheck) : null}
      </p>
    </div>
  );
}
