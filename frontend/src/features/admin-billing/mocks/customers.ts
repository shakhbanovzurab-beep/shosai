import type { Currency, PaidPlanId } from "../domain/contract";
import { createPeople } from "./people";
import { PRICES, paymentMethod } from "./pricing";
import type { Random } from "./random";
import { type Customer, DAY, HOUR } from "./types";

/** About four in five customers pay in rubles, the rest in dollars or euros. */
const pickCurrency = (random: Random) =>
  random.weighted<Currency>(
    [
      [0.8, "RUB"],
      [0.93, "USD"],
    ],
    "EUR",
  );
const pickPlan = (random: Random) =>
  random.weighted<PaidPlanId>(
    [
      [0.72, "professional"],
      [0.97, "team"],
    ],
    "enterprise",
  );

/**
 * Paying customers: a base that signed up before the 12 visible months, then signups growing month over
 * month. Churn is decided later, while their renewals are simulated.
 */
export function generateCustomers(random: Random, now: number, windowStart: number): Customer[] {
  const people = createPeople(random);
  const customers: Customer[] = [];

  const add = (signup: number, plan: PaidPlanId) => {
    const currency = pickCurrency(random);
    const price = PRICES[currency];
    const base = {
      id: `cus_${(10_000 + customers.length).toString(36)}`,
      plan,
      currency,
      method: paymentMethod(random, currency, plan),
      signup,
      churned: null,
    };
    if (plan === "professional") {
      customers.push({ ...base, ...people.person(currency), seats: null, monthly_minor: price.professional });
      return;
    }
    const contact = people.company(currency);
    if (plan === "team") {
      // Team is sold for 2–100 users.
      const seats = random.chance(0.7) ? random.between(2, 12) : random.between(13, 100);
      customers.push({ ...base, ...contact, seats, monthly_minor: seats * price.team_seat });
      return;
    }
    const monthly = random.between(16, 64) * price.enterprise_step;
    customers.push({ ...base, ...contact, seats: null, monthly_minor: monthly });
  };

  for (let i = 0; i < 430; i++) {
    let plan: PaidPlanId = "enterprise";
    if (i < 300) plan = "professional";
    else if (i < 413) plan = "team";
    add(windowStart - random.between(1, 700) * DAY + random.between(6, 20) * HOUR, plan);
  }

  const today = new Date(now);
  for (let m = 0; m < 12; m++) {
    const monthStart = Date.UTC(today.getUTCFullYear(), today.getUTCMonth() - 11 + m, 1);
    const monthEnd = Math.min(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() - 10 + m, 1), now);
    const count = Math.round((44 + m * 3 + random.between(0, 10)) * ((monthEnd - monthStart) / (30 * DAY)));
    for (let i = 0; i < count; i++)
      add(monthStart + Math.floor(random.next() * (monthEnd - monthStart)), pickPlan(random));
  }
  return customers;
}
