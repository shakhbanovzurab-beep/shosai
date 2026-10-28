import { useId, useRef, useState } from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldContent, FieldGroup } from "@/components/ui/field";
import { FieldDescription, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { ApiError } from "@/lib/api/errors";
import { useRouter } from "@/lib/navigation";

import { createBroadcast } from "../../model/create-broadcast";

const TITLE_MAX = 200;

type NewBroadcastDialogProps = { open: boolean; onOpenChange: (open: boolean) => void };

/** Новая трансляция: название и зал ожидания; после создания — студия, где сцена готовится к эфиру. */
export function NewBroadcastDialog({ open, onOpenChange }: NewBroadcastDialogProps) {
  const t = useTranslations("meetingBroadcast");
  const router = useRouter();
  const titleId = useId();
  const waitingId = useId();
  const [title, setTitle] = useState("");
  const [waitingRoom, setWaitingRoom] = useState(false);
  const [creating, setCreating] = useState(false);
  // Один ключ на попытку создать: повтор после сбоя сети не создаст вторую трансляцию.
  const key = useRef<string | null>(null);

  async function create() {
    if (title.trim() === "" || creating) return;
    setCreating(true);
    const idempotencyKey = key.current ?? crypto.randomUUID();
    key.current = idempotencyKey;
    const path = await createBroadcast(title.trim(), waitingRoom, idempotencyKey).catch((error: unknown) =>
      error instanceof ApiError && error.code === "broadcast_not_in_plan" ? "not_in_plan" : null,
    );
    setCreating(false);
    if (path === "not_in_plan") return void toast.error(t("new.notInPlan"));
    if (path === null) return void toast.error(t("new.failed"));
    key.current = null;
    onOpenChange(false);
    router.push(path);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form
          className="flex flex-col gap-5"
          onSubmit={(event) => {
            event.preventDefault();
            void create();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("new.title")}</DialogTitle>
            <DialogDescription>{t("new.description")}</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor={titleId}>{t("new.nameLabel")}</FieldLabel>
              <Input
                id={titleId}
                required
                dir="auto"
                maxLength={TITLE_MAX}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </Field>
            <Field orientation="horizontal">
              <FieldContent>
                <FieldLabel htmlFor={waitingId}>{t("new.waitingRoom")}</FieldLabel>
                <FieldDescription>{t("new.waitingRoomHint")}</FieldDescription>
              </FieldContent>
              <Switch id={waitingId} checked={waitingRoom} onCheckedChange={setWaitingRoom} />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("new.cancel")}
            </Button>
            <Button type="submit" disabled={creating || title.trim() === ""}>
              {creating ? <Spinner data-icon="inline-start" /> : null}
              {t("new.create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
