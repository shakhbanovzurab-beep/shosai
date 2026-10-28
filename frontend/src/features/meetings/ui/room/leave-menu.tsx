import { useState } from "react";

import { ChevronDown, PhoneOff } from "lucide-react";
import { useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";

import type { CallRole } from "../../domain/call";

type LeaveMenuProps = { role: CallRole; onLeave: () => void; onEndForAll: () => void };

/** Выйти самому; владелец может и завершить встречу для всех — с подтверждением, это не отменить. */
export function LeaveMenu({ role, onLeave, onEndForAll }: LeaveMenuProps) {
  const t = useTranslations("meetingRoom");
  const [confirming, setConfirming] = useState(false);
  const leave = (
    <Button variant="destructive" onClick={onLeave}>
      <PhoneOff data-icon="inline-start" />
      {t("leave.leave")}
    </Button>
  );
  if (role !== "owner") return leave;
  return (
    <>
      <ButtonGroup>
        {leave}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="destructive" size="icon" aria-label={t("leave.more")}>
              <ChevronDown aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" side="top">
            <DropdownMenuGroup>
              <DropdownMenuItem onSelect={onLeave}>{t("leave.leave")}</DropdownMenuItem>
              <DropdownMenuItem variant="destructive" onSelect={() => setConfirming(true)}>
                {t("leave.endForAll")}
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </ButtonGroup>
      <ConfirmDestructive
        open={confirming}
        title={t("leave.confirmTitle")}
        description={t("leave.confirmDescription")}
        confirmLabel={t("leave.endForAll")}
        onConfirm={onEndForAll}
        onCancel={() => setConfirming(false)}
      />
    </>
  );
}
