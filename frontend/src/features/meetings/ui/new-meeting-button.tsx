"use client";

import { useRef, useState } from "react";

import { CalendarPlus, ChevronDown, Plus, Video } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";
import { Spinner } from "@/components/ui/spinner";
import { Link, useRouter } from "@/lib/navigation";

import { startMeeting } from "../model/start-meeting";

/**
 * «Начать сейчас» открывает комнату Shosai и входит в неё; встречу на потом планирует «Календарь». Загрузка записи
 * живёт в «Заметках» (meetings A9).
 */
export function NewMeetingButton() {
  const t = useTranslations("meetings");
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  // Один ключ на нажатие «Начать сейчас»: повтор после сбоя сети не создаст вторую комнату.
  const key = useRef<string | null>(null);

  async function start() {
    setStarting(true);
    const idempotencyKey = key.current ?? crypto.randomUUID();
    key.current = idempotencyKey;
    const path = await startMeeting(idempotencyKey).catch(() => null);
    setStarting(false);
    if (path === null) {
      toast.error(t("startFailed"));
      return;
    }
    key.current = null;
    router.push(path);
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button disabled={starting}>
          {starting ? <Spinner data-icon="inline-start" /> : <Plus data-icon="inline-start" />}
          {t("newMeeting")}
          <ChevronDown data-icon="inline-end" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuItem onSelect={() => void start()}>
            <Video />
            {t("actions.startNow")}
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/app/calendar">
              <CalendarPlus />
              {t("actions.schedule")}
            </Link>
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
