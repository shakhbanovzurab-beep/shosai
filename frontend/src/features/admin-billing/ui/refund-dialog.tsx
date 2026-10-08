"use client";

import { type FormEvent, useId, useState, useTransition } from "react";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";

import type { Currency, Transaction } from "../domain/contract";
import { CURRENCY_SYMBOLS, formatAmountInput, formatMoney, parseAmountInput } from "../domain/format";
import { paymentMethodLabel } from "../domain/labels";
import { refundableMinor } from "../domain/refund";
import { refund } from "../model/billing-store";

function amountError(amount: number | null, available: number, currency: Currency) {
  if (amount === null) return "Введите сумму, например 990 или 1 490,50.";
  if (amount > available) return `Можно вернуть не больше ${formatMoney(available, currency)}.`;
  return null;
}

function RefundForm({ transaction, search, onDone }: { transaction: Transaction; search: string; onDone: () => void }) {
  const id = useId();
  const available = refundableMinor(transaction);
  const [value, setValue] = useState(() => formatAmountInput(available));
  const [serverError, setServerError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const amount = parseAmountInput(value);
  const inputError = amountError(amount, available, transaction.currency);
  const error = inputError ?? serverError;
  const partial = amount !== null && amount < available;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (amount === null || inputError) return;
    startTransition(async () => {
      try {
        await refund(transaction, amount, search);
        toast.success("Возврат оформлен", {
          description: `${formatMoney(amount, transaction.currency)} вернутся клиенту ${transaction.customer.name}.`,
        });
        onDone();
      } catch (failure) {
        setServerError(errorMessage(failure) ?? "Не удалось оформить возврат.");
      }
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-6" noValidate>
      <DialogHeader>
        <DialogTitle>Возврат по счёту {transaction.number}</DialogTitle>
        <DialogDescription>
          {transaction.customer.name} получит деньги тем же способом — {paymentMethodLabel(transaction.method)}.
          Отменить возврат будет нельзя.
        </DialogDescription>
      </DialogHeader>

      <Field data-invalid={error ? true : undefined}>
        <FieldLabel htmlFor={`${id}-amount`}>Сумма возврата</FieldLabel>
        <InputGroup>
          <InputGroupInput
            id={`${id}-amount`}
            name="amount"
            inputMode="decimal"
            autoComplete="off"
            value={value}
            aria-invalid={error ? true : undefined}
            aria-describedby={`${id}-hint`}
            disabled={pending}
            onChange={(event) => {
              setValue(event.target.value);
              setServerError(null);
            }}
          />
          <InputGroupAddon align="inline-end">
            <InputGroupText>{CURRENCY_SYMBOLS[transaction.currency]}</InputGroupText>
          </InputGroupAddon>
        </InputGroup>
        <FieldDescription id={`${id}-hint`}>
          Доступно к возврату {formatMoney(available, transaction.currency)}
          {transaction.refunded_minor > 0
            ? ` (уже возвращено ${formatMoney(transaction.refunded_minor, transaction.currency)})`
            : ""}
          .{" "}
          {partial ? (
            <Button
              type="button"
              variant="link"
              className="h-auto p-0 text-sm"
              onClick={() => setValue(formatAmountInput(available))}
            >
              Вернуть всю сумму
            </Button>
          ) : null}
        </FieldDescription>
        {error ? <FieldError aria-live="polite">{error}</FieldError> : null}
      </Field>

      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline" disabled={pending}>
            Отмена
          </Button>
        </DialogClose>
        <Button type="submit" variant="destructive" disabled={pending || error !== null}>
          {pending ? <Spinner data-icon="inline-start" aria-hidden="true" /> : null}
          {amount !== null && !inputError ? `Вернуть ${formatMoney(amount, transaction.currency)}` : "Оформить возврат"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Confirms a full or partial refund; the amount is prefilled with everything still refundable. */
export function RefundDialog({
  transaction,
  search,
  onClose,
}: {
  transaction: Transaction | null;
  search: string;
  onClose: () => void;
}) {
  return (
    <Dialog open={transaction !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md" showCloseButton={false}>
        {transaction ? (
          <RefundForm key={transaction.id} transaction={transaction} search={search} onDone={onClose} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
