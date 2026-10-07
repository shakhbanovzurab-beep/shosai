import type { ChartConfig } from "@/components/ui/chart";

export const leadsChartConfig = {
  newLeads: {
    label: "Новые лиды",
    color: "var(--chart-1)",
  },
  disqualified: {
    label: "Отсеянные",
    color: "var(--chart-3)",
  },
  background: {
    color: "var(--primary)",
  },
} as ChartConfig;

export const proposalsChartConfig = {
  proposalsSent: {
    label: "Отправлено КП",
    color: "var(--chart-1)",
  },
} as ChartConfig;

export const revenueChartConfig = {
  revenue: {
    label: "Выручка",
    color: "var(--chart-1)",
  },
} as ChartConfig;

export const leadsBySourceChartConfig = {
  leads: {
    label: "Лиды",
  },
  website: {
    label: "Сайт",
    color: "var(--chart-1)",
  },
  referral: {
    label: "Рекомендации",
    color: "var(--chart-2)",
  },
  social: {
    label: "Соцсети",
    color: "var(--chart-3)",
  },
  cold: {
    label: "Холодные контакты",
    color: "var(--chart-4)",
  },
  other: {
    label: "Другое",
    color: "var(--chart-5)",
  },
} as ChartConfig;

export const projectRevenueChartConfig = {
  actual: {
    label: "Факт",
    color: "var(--chart-1)",
  },
  remaining: {
    label: "Осталось",
    color: "var(--chart-2)",
  },
  label: {
    color: "var(--primary-foreground)",
  },
} as ChartConfig;

export const salesPipelineChartConfig = {
  value: {
    label: "Лиды",
    color: "var(--chart-1)",
  },
  stage: {
    label: "Этап",
  },
} as ChartConfig;
