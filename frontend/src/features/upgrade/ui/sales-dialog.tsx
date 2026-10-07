"use client";

import { useActionState } from "react";

import { CircleCheck } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

import { COMPANY_MAX, MESSAGE_MAX, TEAM_SIZES, type TeamSize } from "../domain/contract";
import { TEAM_SIZE_RANGES } from "../domain/plan-features";
import { sendSalesInquiry } from "../model/plan-actions";

type FormState = { sent: boolean; error: string | null };

const isTeamSize = (value: string): value is TeamSize => (TEAM_SIZES as readonly string[]).includes(value);

/** The form lives inside the dialog content, so every opening starts from an empty form. */
function SalesForm() {
  const t = useTranslations("upgrade");
  const common = useTranslations("common");
  const [state, submit, pending] = useActionState(
    async (_prev: FormState, form: FormData): Promise<FormState> => {
      const field = (key: string) => String(form.get(key) ?? "").trim();
      const teamSize = field("team_size");
      if (!isTeamSize(teamSize)) return { sent: false, error: t("sales.chooseTeamSize") };
      const error = await sendSalesInquiry(
        {
          work_email: field("work_email"),
          company: field("company"),
          team_size: teamSize,
          message: field("message"),
        },
        t("sales.sendFailed"),
      );
      return { sent: error === null, error };
    },
    { sent: false, error: null },
  );

  if (state.sent) {
    return (
      <div className="flex flex-col items-center gap-3 py-6 text-center">
        <CircleCheck className="size-10 text-primary" aria-hidden="true" />
        <DialogTitle>{t("sales.sentTitle")}</DialogTitle>
        <DialogDescription>{t("sales.sentDescription")}</DialogDescription>
        <DialogClose asChild>
          <Button variant="outline" className="mt-2">
            {t("sales.done")}
          </Button>
        </DialogClose>
      </div>
    );
  }

  return (
    <form action={submit} className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("sales.title")}</DialogTitle>
        <DialogDescription>{t("sales.description")}</DialogDescription>
      </DialogHeader>
      <div className="flex flex-col gap-2">
        <Label htmlFor="sales-email">{t("sales.workEmail")}</Label>
        <Input id="sales-email" name="work_email" type="email" autoComplete="email" required maxLength={254} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="sales-company">{t("sales.company")}</Label>
          <Input id="sales-company" name="company" autoComplete="organization" required maxLength={COMPANY_MAX} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="sales-team">{t("sales.teamSize")}</Label>
          <Select name="team_size" required>
            <SelectTrigger id="sales-team" className="w-full">
              <SelectValue placeholder={t("sales.teamSizePlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {TEAM_SIZES.map((size) => {
                  const { min, max } = TEAM_SIZE_RANGES[size];
                  return (
                    <SelectItem key={size} value={size}>
                      {max === null ? t("sales.teamSizeOpen", { min }) : t("sales.teamSizeRange", { min, max })}
                    </SelectItem>
                  );
                })}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="sales-message">
          {t.rich("sales.message", {
            muted: (chunks) => <span className="font-normal text-muted-foreground">{chunks}</span>,
          })}
        </Label>
        <Textarea
          id="sales-message"
          name="message"
          rows={4}
          maxLength={MESSAGE_MAX}
          placeholder={t("sales.messagePlaceholder")}
        />
      </div>
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="ghost">
            {common("actions.cancel")}
          </Button>
        </DialogClose>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("sales.send")}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Enterprise is sold, not bought: the card's button opens a short request for the sales team. */
export function SalesDialog() {
  const t = useTranslations("upgrade");
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full">
          {t("sales.contact")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <SalesForm />
      </DialogContent>
    </Dialog>
  );
}
