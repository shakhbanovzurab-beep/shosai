"use client";

import { cn } from "cn";
import { useFormatter, useTranslations } from "next-intl";

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
import { getInitials } from "@/lib/utils";

/** Initials in a circle; the name is announced by the text next to it, so the avatar itself is hidden. */
export function PersonAvatar({
  name,
  size = "sm",
  className,
}: {
  name: string;
  size?: "sm" | "default" | "lg";
  className?: string;
}) {
  return (
    <Avatar size={size} aria-hidden="true" className={className}>
      <AvatarFallback className={cn(size === "sm" && "text-[10px]")}>{getInitials(name)}</AvatarFallback>
    </Avatar>
  );
}

/** Up to `max` faces, then "+N"; every name is in the tooltip and the accessible label. */
export function PeopleStack({ names, max = 4, className }: { names: string[]; max?: number; className?: string }) {
  const shown = names.slice(0, max);
  const t = useTranslations("workspace");
  const format = useFormatter();
  const hidden = names.length - shown.length;
  const all = format.list(names, { type: "conjunction" });
  return (
    <AvatarGroup title={all} className={cn("-space-x-1.5", className)}>
      <span className="sr-only">{t("people.list", { names: all })}</span>
      {shown.map((name) => (
        <Avatar key={name} aria-hidden="true">
          <AvatarFallback className="text-[11px]">{getInitials(name)}</AvatarFallback>
        </Avatar>
      ))}
      {hidden > 0 ? (
        <AvatarGroupCount aria-hidden="true" className="text-[11px]">
          {t("people.more", { count: hidden })}
        </AvatarGroupCount>
      ) : null}
    </AvatarGroup>
  );
}

/** An avatar and a name on one line, e.g. a task's assignee; `label` replaces the text, like "You". */
export function PersonLabel({ name, label, className }: { name: string; label?: string; className?: string }) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5", className)}>
      <PersonAvatar name={name} className="size-5" />
      <span dir="auto" className="truncate">
        {label ?? name}
      </span>
    </span>
  );
}
