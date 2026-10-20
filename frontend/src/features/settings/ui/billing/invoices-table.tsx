import { Download, FileText } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CALENDAR_DAY } from "@/i18n/calendar-days";

import type { Invoice } from "../../domain/billing-contract";

/** Billing history: date and number, what was charged, amount, status and a download. */
export function InvoicesTable({ invoices }: { invoices: Invoice[] }) {
  const t = useTranslations("settingsBilling");
  const format = useFormatter();

  if (invoices.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border bg-card p-8 text-center">
        <FileText className="size-10 text-muted-foreground" aria-hidden="true" />
        <p className="text-muted-foreground text-sm">{t("history.empty")}</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead className="px-4 text-start">{t("history.columns.date")}</TableHead>
            <TableHead className="hidden px-4 text-start sm:table-cell">{t("history.columns.description")}</TableHead>
            <TableHead className="px-4 text-start">{t("history.columns.amount")}</TableHead>
            <TableHead className="px-4 text-center">{t("history.columns.status")}</TableHead>
            <TableHead className="w-12 px-4 text-end">
              <span className="sr-only">{t("history.columns.download")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((invoice) => (
            <TableRow key={invoice.id}>
              <TableCell className="px-4">
                {/* Счёт датирован календарным днём: он печатается в UTC, где лежит его полночь. */}
                <div className="font-medium">{format.dateTime(new Date(invoice.date), "medium", CALENDAR_DAY)}</div>
                <div className="font-mono text-muted-foreground text-xs">{invoice.number}</div>
              </TableCell>
              <TableCell dir="auto" className="hidden px-4 sm:table-cell">
                {invoice.description}
              </TableCell>
              <TableCell className="px-4 font-medium tabular-nums">
                {format.number(invoice.amount_cents / 100, { style: "currency", currency: invoice.currency })}
              </TableCell>
              <TableCell className="px-4 text-center">{t(`history.status.${invoice.status}`)}</TableCell>
              <TableCell className="px-4 text-end">
                {invoice.download_url ? (
                  <Button variant="ghost" size="icon-sm" asChild>
                    <a
                      href={invoice.download_url}
                      download
                      aria-label={t("history.download", { number: invoice.number })}
                    >
                      <Download />
                    </a>
                  </Button>
                ) : (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    disabled
                    aria-label={t("history.notReady", { number: invoice.number })}
                  >
                    <Download />
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
