import { cn } from "cn";
import { CircleUserRound } from "lucide-react";
import { useTranslations } from "next-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { getInitials } from "@/lib/utils";

import type { TaskOwnerProfile } from "../domain/board";
import { ownerTones } from "./tones";

/** The owner's avatar, or a placeholder for an unassigned task. */
export function OwnerAvatar({ owner }: { owner: TaskOwnerProfile | null }) {
  if (!owner) return <CircleUserRound className="size-5 text-muted-foreground" aria-hidden="true" />;
  return (
    <Avatar className={cn("size-5 after:rounded-sm", ownerTones[owner.tone])}>
      <AvatarFallback className="rounded-sm text-[10px]">{getInitials(owner.name)}</AvatarFallback>
    </Avatar>
  );
}

/** The owner's name as people wrote it, or "Unassigned" in the user's language. */
export function OwnerName({ owner, className }: { owner: TaskOwnerProfile | null; className?: string }) {
  const t = useTranslations("kanban");
  if (!owner) return <span className={cn("truncate", className)}>{t("card.unassigned")}</span>;
  return (
    <span dir="auto" className={cn("truncate", className)}>
      {owner.name}
    </span>
  );
}
