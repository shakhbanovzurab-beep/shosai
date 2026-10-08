"use client";

import { useActionState, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

import { type AdminWorkspaceDetail, SEATS_LIMIT } from "../domain/contract";
import { formatMoney, plural } from "../domain/format";
import { ROLE_LABEL } from "../domain/labels";
import { changeSeats, transferOwner } from "../model/actions";

type DialogProps = { workspace: AdminWorkspaceDetail; open: boolean; onClose: () => void };

/** Mounted per opening, so it starts from the current number. */
function SeatsForm({
  workspace: w,
  initialSeats,
  onClose,
}: {
  workspace: AdminWorkspaceDetail;
  initialSeats: number;
  onClose: () => void;
}) {
  const [value, setValue] = useState(String(initialSeats));
  const [error, setError] = useState<string | null>(null);
  const seats = Number.parseInt(value, 10);
  const valid = Number.isInteger(seats) && seats >= w.seats_used && seats <= SEATS_LIMIT;
  const [, submit, pending] = useActionState(async () => {
    const failure = await changeSeats(w.id, seats);
    if (failure) setError(failure);
    else onClose();
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>Места в «{w.name}»</DialogTitle>
        <DialogDescription>
          Сейчас занято {plural(w.seats_used, ["место", "места", "мест"])}: участники и неотвеченные приглашения. Меньше
          поставить нельзя.
        </DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="admin-seats">Оплаченных мест</FieldLabel>
          <Input
            id="admin-seats"
            type="number"
            inputMode="numeric"
            min={w.seats_used}
            max={SEATS_LIMIT}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            aria-invalid={!valid}
          />
          <FieldDescription>
            {valid
              ? `В месяц: ${formatMoney(seats * w.plan.price_per_seat_cents, w.plan.currency)} вместо ${formatMoney(w.monthly_cents, w.plan.currency)}`
              : `От ${w.seats_used} до ${SEATS_LIMIT}.`}
          </FieldDescription>
        </Field>
        {error ? <FieldError role="alert">{error}</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>
          Отмена
        </Button>
        <Button type="submit" disabled={pending || !valid || seats === w.plan.seats}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          Сохранить
        </Button>
      </DialogFooter>
    </form>
  );
}

export function SeatsDialog({ workspace, open, onClose }: DialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {open ? <SeatsForm workspace={workspace} initialSeats={workspace.plan.seats} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}

/** Mounted per opening, so nothing is picked at first. */
function OwnerForm({ workspace: w, onClose }: { workspace: AdminWorkspaceDetail; onClose: () => void }) {
  const candidates = w.people.filter((p) => p.role !== "owner");
  const [memberId, setMemberId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const picked = candidates.find((p) => p.id === memberId);
  const [, submit, pending] = useActionState(async () => {
    if (!picked) return null;
    const failure = await transferOwner(w.id, picked.id, picked.name);
    if (failure) setError(failure);
    else onClose();
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>Передать владение «{w.name}»</DialogTitle>
        <DialogDescription>
          Например, если владелец ушёл из компании. Новый владелец получит все права, прежний{" "}
          {w.owner ? `(${w.owner.name}) ` : ""}станет администратором.
        </DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="admin-owner">Новый владелец</FieldLabel>
          <Select value={memberId} onValueChange={setMemberId}>
            <SelectTrigger id="admin-owner" className="w-full">
              <SelectValue placeholder="Выберите участника" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {candidates.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name} · {ROLE_LABEL[p.role].toLowerCase()}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        {error ? <FieldError role="alert">{error}</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>
          Отмена
        </Button>
        <Button type="submit" disabled={pending || !picked}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          Передать
        </Button>
      </DialogFooter>
    </form>
  );
}

export function OwnerDialog({ workspace, open, onClose }: DialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {open ? <OwnerForm workspace={workspace} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}
