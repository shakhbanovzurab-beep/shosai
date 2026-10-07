"use client";

import { useActionState, useState } from "react";

import { useRouter } from "next/navigation";

import { Minus, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

import { SEATS_MAX, SEATS_MIN, WORKSPACE_NAME_MAX } from "../../domain/contract";
import { workspacePath } from "../../domain/paths";
import { createWorkspace } from "../../model/workspace-actions";

const clamp = (value: number) => Math.min(Math.max(value, SEATS_MIN), SEATS_MAX);

/** Name and seats: everything else (people, sharing, knowledge) is set up from Home afterwards. */
export function CreateWorkspaceForm() {
  const t = useTranslations("workspace");
  const router = useRouter();
  const [seats, setSeats] = useState(5);
  const [error, submit, pending] = useActionState(async (_: string | null, form: FormData) => {
    const name = String(form.get("name") ?? "").trim();
    if (!name) return t("create.nameRequired");
    const result = await createWorkspace({ name, seats }, t);
    if ("error" in result) return result.error;
    router.push(workspacePath(result.slug));
    return null;
  }, null);

  return (
    <Card className="shadow-xs">
      <form action={submit} noValidate className="flex flex-col gap-4">
        <CardHeader>
          <CardTitle>{t("createWorkspace")}</CardTitle>
          <CardDescription>{t("create.formHint")}</CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field data-invalid={error ? true : undefined}>
              <FieldLabel htmlFor="workspace-name">{t("create.name")}</FieldLabel>
              <Input
                id="workspace-name"
                name="name"
                required
                maxLength={WORKSPACE_NAME_MAX}
                placeholder={t("create.namePlaceholder")}
                dir="auto"
                autoComplete="organization"
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? "workspace-error" : undefined}
              />
              {error ? <FieldError id="workspace-error">{error}</FieldError> : null}
            </Field>
            <Field>
              <FieldLabel htmlFor="workspace-seats">{t("create.seats")}</FieldLabel>
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  aria-label={t("create.fewerSeats")}
                  disabled={seats <= SEATS_MIN}
                  onClick={() => setSeats((n) => clamp(n - 1))}
                >
                  <Minus />
                </Button>
                <Input
                  id="workspace-seats"
                  type="number"
                  inputMode="numeric"
                  min={SEATS_MIN}
                  max={SEATS_MAX}
                  value={seats}
                  onChange={(event) => {
                    const next = Number.parseInt(event.currentTarget.value, 10);
                    if (Number.isFinite(next)) setSeats(clamp(next));
                  }}
                  className="w-16 text-center tabular-nums [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  aria-label={t("create.moreSeats")}
                  disabled={seats >= SEATS_MAX}
                  onClick={() => setSeats((n) => clamp(n + 1))}
                >
                  <Plus />
                </Button>
              </div>
              <FieldDescription>{t("create.seatsHint", { min: SEATS_MIN, max: SEATS_MAX })}</FieldDescription>
            </Field>
          </FieldGroup>
        </CardContent>
        <CardFooter>
          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? <Spinner data-icon="inline-start" /> : null}
            {t("create.submit")}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
