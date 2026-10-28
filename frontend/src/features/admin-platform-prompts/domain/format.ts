const numberFormat = new Intl.NumberFormat("ru-RU");
const dateTimeFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" });

export const formatNumber = (value: number) => numberFormat.format(value);
export const formatDateTime = (iso: string) => dateTimeFormat.format(new Date(iso));
