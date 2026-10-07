"use client";

import type { ReactNode } from "react";

import Link from "next/link";

import { cn } from "cn";
import { ArrowUpRight, Bug, Mail } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { pluralizeRu } from "@/lib/plural";
import { getInitials } from "@/lib/utils";

import type { ConversationDetail } from "../domain/contract";
import { formatLongDate, formatShortDate } from "../domain/format";
import { PLAN_LABELS, STATUS_LABELS } from "../domain/labels";
import { ChannelLabel } from "./meta";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="min-w-0 break-words text-sm">{children}</dd>
    </div>
  );
}

/** Who the user is: plan, app and OS, recent errors, and their other conversations. */
export function UserProfile({
  conversation,
  onOpenConversation,
  className,
}: {
  conversation: ConversationDetail;
  onOpenConversation: (id: string) => void;
  className?: string;
}) {
  const { profile, past_conversations: past } = conversation;
  const errors = profile.recent_errors;
  const errorsHref = `/admin/errors?user=${encodeURIComponent(profile.email)}`;

  return (
    <div className={cn("flex flex-col gap-6 p-4", className)}>
      <div className="flex flex-col items-center gap-2 text-center">
        <Avatar size="lg" className="size-14">
          <AvatarFallback className="bg-muted text-base text-foreground">{getInitials(profile.name)}</AvatarFallback>
        </Avatar>
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="font-semibold">{profile.name}</span>
          <a
            href={`mailto:${profile.email}`}
            className="inline-flex items-center justify-center gap-1 break-all text-muted-foreground text-xs underline-offset-2 hover:underline"
          >
            <Mail className="size-3 shrink-0" aria-hidden="true" />
            {profile.email}
          </a>
        </div>
        <Badge variant="secondary">{PLAN_LABELS[profile.plan]}</Badge>
      </div>

      <dl className="grid grid-cols-1 gap-3">
        <Field label="Приложение">{profile.app_version}</Field>
        <Field label="Система">{profile.os}</Field>
        <Field label="Канал обращения">
          <ChannelLabel channel={conversation.channel} />
        </Field>
        <Field label="Регистрация">{formatLongDate(profile.signed_up_at)}</Field>
        <Field label="Ошибки за 7 дней">
          {errors > 0 ? (
            <Link
              href={errorsHref}
              className="inline-flex items-center gap-1 font-medium text-destructive underline-offset-2 hover:underline"
            >
              <Bug className="size-3.5" aria-hidden="true" />
              {errors} {pluralizeRu(errors, ["ошибка", "ошибки", "ошибок"])}
              <ArrowUpRight className="size-3.5" aria-hidden="true" />
            </Link>
          ) : (
            <span className="text-muted-foreground">Ошибок нет</span>
          )}
        </Field>
      </dl>

      <section aria-labelledby="past-conversations-title" className="flex flex-col gap-2">
        <h3 id="past-conversations-title" className="font-medium text-muted-foreground text-xs">
          Другие обращения
        </h3>
        {past.length === 0 ? (
          <p className="text-muted-foreground text-sm">Это первое обращение пользователя.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {past.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onOpenConversation(item.id)}
                  className="flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  <span className="line-clamp-1 text-sm">{item.subject}</span>
                  <span className="text-muted-foreground text-xs">
                    #{item.number} · {STATUS_LABELS[item.status]} · {formatShortDate(item.updated_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
