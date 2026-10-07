"use client";

import { Download, MoreHorizontal, Undo2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type { Transaction } from "../domain/contract";
import { refundableMinor } from "../domain/refund";

export function TransactionActions({
  transaction,
  onRefund,
}: {
  transaction: Transaction;
  onRefund: (transaction: Transaction) => void;
}) {
  const canRefund = refundableMinor(transaction) > 0;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={`Действия с платежом ${transaction.number}`}>
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuItem disabled={!canRefund} onSelect={() => onRefund(transaction)}>
          <Undo2 aria-hidden="true" />
          Оформить возврат
        </DropdownMenuItem>
        {transaction.invoice_url ? (
          <DropdownMenuItem asChild>
            <a href={transaction.invoice_url} download>
              <Download aria-hidden="true" />
              Скачать счёт
            </a>
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem disabled>
            <Download aria-hidden="true" />
            Счёт не выставлен
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
