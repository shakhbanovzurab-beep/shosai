import { parse } from "date-fns";

const JOINED_DATE_PATTERN = "dd MMM yyyy, h:mm a";

const joinedDateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  month: "short",
  year: "numeric",
});

export function parseJoinedDate(value: string) {
  return parse(value, JOINED_DATE_PATTERN, new Date());
}

export function formatJoinedDate(value: string) {
  const date = parseJoinedDate(value);

  return Number.isNaN(date.getTime()) ? value : joinedDateFormatter.format(date);
}
