export const leadsChartData = [
  { date: "1-5", newLeads: 120, disqualified: 40 },
  { date: "6-10", newLeads: 95, disqualified: 30 },
  { date: "11-15", newLeads: 60, disqualified: 22 },
  { date: "16-20", newLeads: 100, disqualified: 35 },
  { date: "21-25", newLeads: 150, disqualified: 70 },
  { date: "26-30", newLeads: 110, disqualified: 60 },
];

export const proposalsChartData = [
  { date: "1-5", proposalsSent: 9 },
  { date: "6-10", proposalsSent: 16 },
  { date: "11-15", proposalsSent: 6 },
  { date: "16-20", proposalsSent: 18 },
  { date: "21-25", proposalsSent: 11 },
  { date: "26-30", proposalsSent: 14 },
];

export const revenueChartData = [
  { month: "июль 2024", revenue: 6700 },
  { month: "август 2024", revenue: 7100 },
  { month: "сентябрь 2024", revenue: 6850 },
  { month: "октябрь 2024", revenue: 7500 },
  { month: "ноябрь 2024", revenue: 8000 },
  { month: "декабрь 2024", revenue: 8300 },
  { month: "январь 2025", revenue: 7900 },
  { month: "февраль 2025", revenue: 8400 },
  { month: "март 2025", revenue: 8950 },
  { month: "апрель 2025", revenue: 9700 },
  { month: "май 2025", revenue: 11200 },
  { month: "июнь 2025", revenue: 9500 },
];

export const leadsBySourceChartData = [
  { source: "website", leads: 170, fill: "var(--color-website)" },
  { source: "referral", leads: 105, fill: "var(--color-referral)" },
  { source: "social", leads: 90, fill: "var(--color-social)" },
  { source: "cold", leads: 62, fill: "var(--color-cold)" },
  { source: "other", leads: 48, fill: "var(--color-other)" },
];

export const projectRevenueChartData = [
  { name: "Разработка MVP", actual: 82000, target: 90000 },
  { name: "Консалтинг", actual: 48000, target: 65000 },
  { name: "Сайты на Framer", actual: 34000, target: 45000 },
  { name: "Поддержка DevOps", actual: 77000, target: 90000 },
  { name: "Обучение LLM", actual: 68000, target: 80000 },
  { name: "Запуск продукта", actual: 52000, target: 70000 },
].map((row) => ({
  ...row,
  remaining: Math.max(0, row.target - row.actual),
}));

export const salesPipelineChartData = [
  { stage: "Лиды", value: 680, fill: "var(--chart-1)" },
  { stage: "Квалифицированы", value: 480, fill: "var(--chart-2)" },
  { stage: "КП отправлено", value: 210, fill: "var(--chart-3)" },
  { stage: "Переговоры", value: 120, fill: "var(--chart-4)" },
  { stage: "Выиграно", value: 45, fill: "var(--chart-5)" },
];
