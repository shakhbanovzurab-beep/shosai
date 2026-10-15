import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";

import type { AdminUserCard } from "../domain/contract";
import { formatDate, formatDateTime } from "../domain/format";
import { homeLabel } from "../domain/labels";
import { AccountActions } from "./account-actions";
import { StateBadge } from "./state-badge";

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm tabular-nums">{children}</dd>
    </div>
  );
}

/** Состояние и дом, имя и почта, факты профиля и то, что администратор может сделать. */
export function UserHeader({ card }: { card: AdminUserCard }) {
  const { user } = card;
  return (
    <header className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <StateBadge state={user.state} />
        <Badge variant="outline">Дом данных: {homeLabel(user.home)}</Badge>
      </div>
      <h1 className="break-words font-semibold text-xl tracking-tight">
        {user.full_name || user.display_name || user.email}
      </h1>
      <p className="break-all text-muted-foreground text-sm">{user.email}</p>
      <dl className="flex flex-wrap gap-x-8 gap-y-3">
        {user.display_name ? <Fact label="Обращение">{user.display_name}</Fact> : null}
        {card.work_role ? <Fact label="Род занятий">{card.work_role}</Fact> : null}
        <Fact label="Страна">{card.country ?? "не указана"}</Fact>
        <Fact label="Язык">{card.language}</Fact>
        <Fact label="Часовой пояс">{card.timezone ?? "не указан"}</Fact>
        <Fact label="Почта подтверждена">{card.email_verified_at ? formatDate(card.email_verified_at) : "нет"}</Fact>
        <Fact label="Создан">
          <time dateTime={user.created_at}>{formatDate(user.created_at)}</time>
        </Fact>
        <Fact label="Последний вход">
          {user.last_login_at ? (
            <time dateTime={user.last_login_at}>{formatDateTime(user.last_login_at)}</time>
          ) : (
            "ещё не входил"
          )}
        </Fact>
      </dl>
      <AccountActions card={card} />
    </header>
  );
}
