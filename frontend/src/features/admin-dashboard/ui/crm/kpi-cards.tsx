import { ArrowUpRight, TrendingDown, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader } from "@/components/ui/card";

const usdFormatter = new Intl.NumberFormat("ru-RU", {
  currency: "USD",
  maximumFractionDigits: 0,
  style: "currency",
});

export function KpiCards() {
  return (
    <section className="space-y-5">
      <div className="space-y-1">
        <h2 className="text-3xl tracking-tight">Обзор воронки</h2>
        <p className="text-muted-foreground text-sm">
          Следите за качеством лидов, открытыми сделками и конверсией в текущем цикле продаж.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Объём воронки лидов</CardDescription>
            <CardAction>
              <ArrowUpRight className="size-4" />
            </CardAction>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-3xl leading-none tracking-tight">{usdFormatter.format(284_500)}</span>

              <Badge
                variant="outline"
                className="border-green-200 bg-green-500/10 text-green-700 dark:border-green-900/40 dark:bg-green-500/15 dark:text-green-300"
              >
                <TrendingUp />
                +12%
              </Badge>
            </div>
            <p className="text-sm">
              <span className="font-medium text-foreground">{usdFormatter.format(254_200)}</span>{" "}
              <span className="text-muted-foreground">в прошлом месяце</span>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Доля квалифицированных лидов</CardDescription>
            <CardAction>
              <ArrowUpRight className="size-4" />
            </CardAction>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-3xl leading-none tracking-tight">28,4%</span>

              <Badge variant="outline" className="border-destructive/20 bg-destructive/10 text-destructive">
                <TrendingDown />
                −2,5%
              </Badge>
            </div>
            <p className="text-sm">
              <span className="font-medium text-foreground">30,9%</span>{" "}
              <span className="text-muted-foreground">в прошлом месяце</span>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Открытые сделки</CardDescription>
            <CardAction>
              <ArrowUpRight className="size-4" />
            </CardAction>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-3xl leading-none tracking-tight">42</span>

              <Badge
                variant="outline"
                className="border-green-200 bg-green-500/10 text-green-700 dark:border-green-900/40 dark:bg-green-500/15 dark:text-green-300"
              >
                <TrendingUp />
                +7
              </Badge>
            </div>
            <p className="text-sm">
              <span className="font-medium text-foreground">35</span>{" "}
              <span className="text-muted-foreground">в прошлом месяце</span>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Конверсия лидов в сделки</CardDescription>
            <CardAction>
              <ArrowUpRight className="size-4" />
            </CardAction>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-3xl leading-none tracking-tight">18,1%</span>

              <Badge
                variant="outline"
                className="border-green-200 bg-green-500/10 text-green-700 dark:border-green-900/40 dark:bg-green-500/15 dark:text-green-300"
              >
                <TrendingUp />
                +1,6%
              </Badge>
            </div>
            <p className="text-sm">
              <span className="font-medium text-foreground">16,5%</span>{" "}
              <span className="text-muted-foreground">в прошлом месяце</span>
            </p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
