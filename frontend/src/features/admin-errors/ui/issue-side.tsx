import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { IssueDetail } from "../domain/contract";

function Facts({ items }: { items: [label: string, value: ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words text-right">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function IssueSide({ issue }: { issue: IssueDetail }) {
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Окружение</CardTitle>
        </CardHeader>
        <CardContent>
          <Facts
            items={[
              ["Устройство", issue.context.device],
              ["ОС", issue.context.os_version],
              [
                "Версия",
                <span key="v" className="font-mono">
                  {issue.context.app_version}
                </span>,
              ],
              ["Язык", issue.context.locale ?? "—"],
            ]}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Пользователь</CardTitle>
        </CardHeader>
        <CardContent>
          {issue.user ? (
            <Facts
              items={[
                ["Имя", issue.user.name],
                ["Email", issue.user.email],
                [
                  "ID",
                  <span key="id" className="font-mono text-xs">
                    {issue.user.id}
                  </span>,
                ],
              ]}
            />
          ) : (
            <p className="text-muted-foreground text-sm">Событие пришло без пользователя (вход не выполнен).</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Теги</CardTitle>
        </CardHeader>
        <CardContent>
          {issue.tags.length === 0 ? (
            <p className="text-muted-foreground text-sm">Тегов нет.</p>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {issue.tags.map((tag) => (
                <li key={tag.key} className="flex overflow-hidden rounded-md border font-mono text-xs">
                  <span className="bg-muted px-1.5 py-0.5 text-muted-foreground">{tag.key}</span>
                  <span className="break-all px-1.5 py-0.5">{tag.value}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
