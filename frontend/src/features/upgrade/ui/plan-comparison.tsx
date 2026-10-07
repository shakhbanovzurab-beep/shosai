import { Check, Minus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { Plan } from "../domain/contract";
import { type Cell, COMPARISON_ROWS } from "../domain/plan-features";
import { usePlanWords } from "./use-plan-words";

function Value({ cell }: { cell: Cell }) {
  const t = useTranslations("upgradePlans");
  const words = usePlanWords();
  if (cell === true) {
    return (
      <>
        <Check className="mx-auto size-4 text-primary" aria-hidden="true" />
        <span className="sr-only">{t("compare.included")}</span>
      </>
    );
  }
  if (cell === false) {
    return (
      <>
        <Minus className="mx-auto size-4 text-muted-foreground" aria-hidden="true" />
        <span className="sr-only">{t("compare.notIncluded")}</span>
      </>
    );
  }
  return <>{words.cell(cell)}</>;
}

/** Every limit and feature side by side, for the details the cards leave out. */
export function PlanComparison({ plans }: { plans: Plan[] }) {
  const t = useTranslations("upgradePlans");
  return (
    <section aria-labelledby="compare-plans" className="flex flex-col gap-3">
      <h2 id="compare-plans" className="font-medium text-lg">
        {t("compare.title")}
      </h2>
      <div className="overflow-hidden rounded-xl border bg-card">
        <Table>
          <TableHeader className="bg-muted/50">
            <TableRow>
              <TableHead className="ps-4 text-start">{t("compare.feature")}</TableHead>
              {plans.map((plan) => (
                <TableHead key={plan.id} className="text-center">
                  {plan.name}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {COMPARISON_ROWS.map(({ row, cell }) => (
              <TableRow key={row}>
                <TableHead scope="row" className="ps-4 text-start font-normal text-foreground">
                  {t(`compare.rows.${row}`)}
                </TableHead>
                {plans.map((plan) => (
                  <TableCell key={plan.id} className="text-center">
                    <Value cell={cell(plan)} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}
