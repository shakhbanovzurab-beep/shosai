import {
  CURRENCIES,
  type Currency,
  PLAN_CAPABILITIES,
  type Plan,
  type PlanAudience,
  type PlanCapabilities,
  type Prices,
} from "./contract";
import { moneyInput, optionalIntInput, parseInt10, parseMoney, parseOptionalInt } from "./format";

/* The plan form's text state and its conversion to and from the API's PlanDraft. */

export type PriceInputs = Record<Currency, string>;
export type PricePeriod = "price_monthly" | "price_yearly";

export type PlanValues = {
  name: string;
  slug: string;
  description: string;
  audience: PlanAudience;
  /** Used only by team plans; other plans are single-user. */
  seats_min: string;
  seats_max: string;
  custom_pricing: boolean;
  price_monthly: PriceInputs;
  price_yearly: PriceInputs;
  meeting_minutes_per_month: string;
  file_manager_gb: string;
  knowledge_base_mb: string;
  room_participants: string;
  capabilities: PlanCapabilities;
  features: string;
  is_active: boolean;
  is_featured: boolean;
  sort_order: string;
};

/** Text fields only: the ones edited through a plain input. */
export type PlanTextKey = { [K in keyof PlanValues]: PlanValues[K] extends string ? K : never }[keyof PlanValues];

const FREE: PriceInputs = { RUB: "0", USD: "0", EUR: "0" };

export const EMPTY_PLAN: PlanValues = {
  name: "",
  slug: "",
  description: "",
  audience: "individual",
  seats_min: "2",
  seats_max: "",
  custom_pricing: false,
  price_monthly: FREE,
  price_yearly: FREE,
  meeting_minutes_per_month: "",
  file_manager_gb: "",
  knowledge_base_mb: "",
  room_participants: "",
  capabilities: Object.fromEntries(PLAN_CAPABILITIES.map((c) => [c, false])) as PlanCapabilities,
  features: "",
  is_active: true,
  is_featured: false,
  sort_order: "0",
};

const priceInputs = (prices: Prices) =>
  Object.fromEntries(CURRENCIES.map((c) => [c, moneyInput(prices[c])])) as PriceInputs;
const parsePrices = (inputs: PriceInputs) =>
  Object.fromEntries(CURRENCIES.map((c) => [c, parseMoney(inputs[c])])) as Prices;

export function planValuesOf(plan: Plan): PlanValues {
  return {
    name: plan.name,
    slug: plan.slug,
    description: plan.description,
    audience: plan.audience,
    seats_min: plan.seats ? String(plan.seats.min) : "2",
    seats_max: optionalIntInput(plan.seats?.max ?? null),
    custom_pricing: plan.custom_pricing,
    price_monthly: priceInputs(plan.price_monthly),
    price_yearly: priceInputs(plan.price_yearly),
    meeting_minutes_per_month: optionalIntInput(plan.limits.meeting_minutes_per_month),
    file_manager_gb: optionalIntInput(plan.limits.file_manager_gb),
    knowledge_base_mb: optionalIntInput(plan.limits.knowledge_base_mb),
    room_participants: optionalIntInput(plan.limits.room_participants ?? null),
    capabilities: { ...plan.capabilities },
    features: plan.features.join("\n"),
    is_active: plan.is_active,
    is_featured: plan.is_featured,
    sort_order: String(plan.sort_order),
  };
}

/** The draft to validate; unparseable numbers become NaN so the schema reports them. */
export function planCandidateOf(values: PlanValues) {
  return {
    name: values.name,
    slug: values.slug,
    description: values.description,
    audience: values.audience,
    seats:
      values.audience === "team"
        ? { min: parseInt10(values.seats_min), max: parseOptionalInt(values.seats_max) }
        : null,
    custom_pricing: values.custom_pricing,
    // A custom-priced plan stores no price, whatever the hidden price inputs still hold.
    price_monthly: values.custom_pricing ? parsePrices(FREE) : parsePrices(values.price_monthly),
    price_yearly: values.custom_pricing ? parsePrices(FREE) : parsePrices(values.price_yearly),
    limits: {
      meeting_minutes_per_month: parseOptionalInt(values.meeting_minutes_per_month),
      file_manager_gb: parseOptionalInt(values.file_manager_gb),
      knowledge_base_mb: parseOptionalInt(values.knowledge_base_mb),
      room_participants: parseOptionalInt(values.room_participants),
    },
    capabilities: values.capabilities,
    features: values.features
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    is_active: values.is_active,
    is_featured: values.is_featured,
    sort_order: parseInt10(values.sort_order),
  };
}

/** Error keys from validation paths: `limits.file_manager_gb` → `file_manager_gb`, `features.3` → `features`, `price_yearly.USD` kept. */
export function planFieldKey(path: string) {
  if (path.startsWith("limits.")) return path.slice("limits.".length);
  if (path.startsWith("seats.")) return `seats_${path.slice("seats.".length)}`;
  if (path.startsWith("features")) return "features";
  return path;
}

export const planInputId = (key: string) => `plan-${key.replaceAll("_", "-").replaceAll(".", "-")}`;

/** How much cheaper a year is than 12 monthly payments, from the rouble prices. */
export function yearlyHint(values: PlanValues) {
  const monthly = parseMoney(values.price_monthly.RUB);
  const yearly = parseMoney(values.price_yearly.RUB);
  if (!(monthly > 0) || !(yearly >= 0)) return "Годовая цена — сумма за 12 месяцев. 0 во всех валютах — бесплатно.";
  const saving = Math.round((1 - yearly / (monthly * 12)) * 100);
  if (saving > 0) return `Год дешевле 12 месяцев на ${saving}% (по рублёвой цене).`;
  if (saving < 0) return "Годовая цена выше, чем 12 месяцев помесячной оплаты.";
  return "Без скидки за годовую оплату.";
}
