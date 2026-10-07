export const stageLabels: Record<string, string> = {
  "Proposal Sent": "КП отправлено",
  Discovery: "Выявление потребностей",
  Negotiation: "Переговоры",
  Qualified: "Квалифицирован",
};

export const healthLabels: Record<string, string> = {
  "On Track": "По плану",
  "Needs Review": "Требует проверки",
  "At Risk": "Под угрозой",
  "On Hold": "Приостановлено",
};

const NON_NUMERIC_PATTERN = /[^0-9.]/g;

const usdFormatter = new Intl.NumberFormat("ru-RU", {
  currency: "USD",
  maximumFractionDigits: 0,
  style: "currency",
});

export function formatUsdValue(value: string) {
  const amount = Number(value.replace(NON_NUMERIC_PATTERN, ""));

  return Number.isFinite(amount) ? usdFormatter.format(amount) : value;
}
