import type { ReactNode } from "react";

import { KeyRound, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { LiveKitServer } from "../domain/contract";
import { formatDuration } from "../domain/format";
import { HealthBadge } from "./status-badge";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="min-w-0 text-sm">{children}</dd>
    </div>
  );
}

const NOT_SET = <span className="text-muted-foreground">Не указано</span>;

export function ServerStatusCard({ server, updatedAt }: { server: LiveKitServer; updatedAt: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Сервер</CardTitle>
        <CardDescription>
          {server.demo
            ? "Демо-данные: подключите бэкенд, чтобы видеть реальное состояние LiveKit."
            : "Состояние сервера LiveKit, через который идут встречи Leo."}
        </CardDescription>
        <CardAction className="flex items-center gap-2">
          {server.demo ? <Badge variant="outline">Демо</Badge> : null}
          <HealthBadge health={server.health} />
        </CardAction>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))]">
          <Field label="Адрес">
            {server.url ? <span className="break-all font-mono text-xs leading-5">{server.url}</span> : NOT_SET}
          </Field>
          <Field label="Версия">
            {server.version ? <span className="tabular-nums">{server.version}</span> : NOT_SET}
          </Field>
          <Field label="Регион">{server.region ?? NOT_SET}</Field>
          <Field label="Время работы">
            {server.started_at ? (
              <span className="tabular-nums">{formatDuration(server.started_at, updatedAt)}</span>
            ) : (
              NOT_SET
            )}
          </Field>
          <Field label="API-ключ">
            {server.api_key_configured ? (
              <span className="inline-flex items-center gap-1.5">
                <KeyRound aria-hidden="true" className="size-4 text-green-600 dark:text-green-400" />
                Настроен
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5">
                <ShieldAlert aria-hidden="true" className="size-4 text-amber-600 dark:text-amber-400" />
                Не настроен
              </span>
            )}
          </Field>
        </dl>
      </CardContent>
    </Card>
  );
}
