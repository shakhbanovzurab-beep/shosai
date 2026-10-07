import { cn } from "cn";
import {
  CircleAlert,
  Globe,
  Info,
  type LucideIcon,
  MousePointerClick,
  Navigation,
  Terminal,
  TriangleAlert,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { Breadcrumb, BreadcrumbCategory } from "../domain/contract";
import { formatTime } from "../domain/format";

const CATEGORY: Record<BreadcrumbCategory, { label: string; icon: LucideIcon }> = {
  navigation: { label: "Переход", icon: Navigation },
  http: { label: "Запрос", icon: Globe },
  ui: { label: "Интерфейс", icon: MousePointerClick },
  console: { label: "Консоль", icon: Terminal },
  system: { label: "Система", icon: Info },
};

/** Warnings and errors use their own mark; info keeps the category's icon. */
const LEVEL_ICON: Partial<Record<Breadcrumb["level"], LucideIcon>> = { error: CircleAlert, warning: TriangleAlert };

export function IssueBreadcrumbs({ breadcrumbs }: { breadcrumbs: Breadcrumb[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Хлебные крошки</CardTitle>
        <CardDescription>Что происходило перед ошибкой, по порядку</CardDescription>
      </CardHeader>
      <CardContent>
        {breadcrumbs.length === 0 ? (
          <p className="text-muted-foreground text-sm">Клиент не прислал хлебные крошки.</p>
        ) : (
          <ol className="flex flex-col">
            {breadcrumbs.map((crumb) => {
              const meta = CATEGORY[crumb.category];
              const Icon = LEVEL_ICON[crumb.level] ?? meta.icon;
              return (
                <li
                  key={`${crumb.timestamp}-${crumb.category}-${crumb.message}`}
                  className="grid grid-cols-[auto_1fr_auto] items-start gap-3 border-b py-2 text-sm last:border-b-0"
                >
                  <Icon
                    aria-hidden="true"
                    className={cn(
                      "mt-0.5 size-4",
                      crumb.level === "error" && "text-red-600 dark:text-red-400",
                      crumb.level === "warning" && "text-amber-600 dark:text-amber-400",
                      crumb.level === "info" && "text-muted-foreground",
                    )}
                  />
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="text-muted-foreground text-xs">
                      {meta.label}
                      {crumb.level !== "info" ? ` · ${crumb.level === "error" ? "ошибка" : "предупреждение"}` : null}
                    </span>
                    <span className="break-words font-mono text-xs">{crumb.message}</span>
                  </div>
                  <time dateTime={crumb.timestamp} className="text-muted-foreground text-xs tabular-nums">
                    {formatTime(crumb.timestamp)}
                  </time>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
