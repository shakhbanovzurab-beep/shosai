"use client";

import { Button } from "@/components/ui/button";
import { DialogClose, DialogFooter } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";

/** The server's answer when it refuses a valid-looking form, then Cancel and the submit button. */
export function FormFooter({
  error,
  pending,
  submitLabel,
}: {
  error: string | null;
  pending: boolean;
  submitLabel: string;
}) {
  return (
    <>
      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-destructive text-sm"
        >
          {error}
        </p>
      ) : null}
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline" disabled={pending}>
            Отмена
          </Button>
        </DialogClose>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" aria-label="Сохранение" /> : null}
          {submitLabel}
        </Button>
      </DialogFooter>
    </>
  );
}
