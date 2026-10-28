import { Ellipsis } from "lucide-react";
import { useTranslations } from "use-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";

import {
  type BroadcastSession,
  mayManageCohosts,
  mayModerate,
  type StageMember,
  type StageRole,
} from "../../domain/broadcast";
import { initialsOf } from "../../domain/call";

type StageMembersProps = { members: StageMember[]; self: string; role: StageRole | null; session: BroadcastSession };

/** Сцена: роли и эфир; ведущий и соведущие убирают из эфира и со сцены, соведущих назначает только ведущий. */
export function StageMembers({ members, self, role, session }: StageMembersProps) {
  const t = useTranslations("meetingBroadcast");
  return (
    <ul className="flex flex-col gap-2 overflow-y-auto">
      {members.map((member) => {
        const own = member.identity === self;
        const manageable = mayModerate(role) && !own && member.role !== "host";
        return (
          <li key={member.principal} className="flex items-center gap-2">
            <Avatar className="size-8">
              <AvatarFallback>{initialsOf(member.name)}</AvatarFallback>
            </Avatar>
            <div className="flex min-w-0 flex-1 flex-col">
              <span dir="auto" className="truncate text-sm">
                {member.name}
                {own ? <span className="text-muted-foreground"> ({t("stage.you")})</span> : null}
              </span>
              <span className="flex gap-1 text-muted-foreground text-xs">
                {t(`roles.${member.role}`)}
                {member.onAir ? null : <Badge variant="outline">{t("stage.offAir")}</Badge>}
              </span>
            </div>
            {manageable ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="icon-sm" variant="ghost" aria-label={t("stage.actions", { name: member.name })}>
                    <Ellipsis aria-hidden="true" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => void session.setOnAir(member.principal, !member.onAir)}>
                    {t(member.onAir ? "stage.takeOffAir" : "stage.putOnAir")}
                  </DropdownMenuItem>
                  {mayManageCohosts(role) ? (
                    <DropdownMenuItem
                      onSelect={() => void session.setCohost(member.principal, member.role !== "cohost")}
                    >
                      {t(member.role === "cohost" ? "stage.removeCohost" : "stage.makeCohost")}
                    </DropdownMenuItem>
                  ) : null}
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={() => void session.removeFromStage(member.principal)}
                  >
                    {t("stage.remove")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
