# ADR 0058 — Time zones: the person's zone in the cabinet, one business zone for totals

- **Status:** accepted by the owner on 2026-10-20, after identity's step 16 (the cabinet's time zone).
- **Packages:** identity (the profile's zone, steps 16–17), the cabinet (`frontend/src/i18n`), billing, telemetry, calendar, F6 (`core/ai/spend`), the admin panel.
- **Context documents:** [ARCHITECTURE](../design/ARCHITECTURE.md) §8.2, §19; [identity plan](../plan/slices/identity.md) steps 16–17; [billing plan](../plan/slices/billing.md); [STATUS](../plan/STATUS.md) (calendar, telemetry); `frontend/docs/i18n.md`.

## Context

Until identity's step 16 the cabinet formatted every date in UTC: a meeting at 15:32 UTC read 15:32 for a person in Moscow, and "today" ended at 03:00 their time. Step 16 moved the cabinet to the person's zone and left three questions to the owner: the calendar, whose grid runs on the browser's local time; the admin panel and the server's totals, which count days and months in UTC; and how a profile gets a zone at all, since nothing set one.

## Decision

1. **The cabinet shows a person's time in their zone.** It is the profile's zone (`GET /v1/me`, `timezone`), and the browser's when the profile has none or names one the browser does not know. Moments print in it and calendar days are counted in it; a value that is a calendar day (a due date, an invoice day, a card's expiry) keeps its day in every zone. This is identity's step 16.
2. **The profile gets its zone by itself, unless the person fixes one.** Registration — by code, by password and through a social provider — saves the browser's zone in the profile. Settings › Account offers the zone with "Automatic" by default: in that mode the zone follows the browser each time the person enters the cabinet. Choosing a zone by hand fixes it, and it no longer changes by itself until the person picks "Automatic" again. This is identity's step 17.
3. **The calendar keeps the browser's local time for now.** Its grid (FullCalendar) and its demo events run on the browser's clock, so its event labels stay there too. It moves to the profile's zone together with its own API, in the calendar slice.
4. **One business time zone for the platform: Europe/Moscow.** Every daily and monthly total the server keeps — revenue and payments, AI spend and its daily and monthly limits, usage periods, reports — counts its days and months in the business zone, not in UTC, the browser's or a profile's zone. The admin panel shows its dates and times in the business zone, labelled "МСК". The business zone is a platform setting (`BUSINESS_TIME_ZONE`, default `Europe/Moscow`), read by the backend's settings and handed to the admin panel; it never comes from a browser or a profile.

## Consequences

- Moments stay stored as `timestamptz` in UTC; only the boundaries of days and months move. A day total runs from 00:00 to 24:00 Moscow time, which is 21:00 to 21:00 UTC.
- What counts in UTC today moves to the business zone in the steps that own it:
  - billing: revenue and payment totals, the month of a person's minutes and the Monday week of tokens, promo codes' validity days, the admin billing and plans screens (billing plan, "Business time zone" step);
  - F6's spend reports and limits in `core/ai/spend` (day and month starts, the daily series, the per-user daily alert) and the admin AI models screen move in the same billing step, so money and spend change their day boundary together;
  - telemetry: its product reports and the admin dashboard's telemetry block count days and months in the business zone from their first step.
- Until a step moves its totals, the admin panel keeps showing UTC: a screen moves to "МСК" together with the totals it shows, so a day on screen is always the server's day.
- How billing's step 7b applied it (2026-10-21): the platform reads `BUSINESS_TIME_ZONE` once and hands a `BusinessCalendar` (`core/kernel/business_calendar.py`) to every service that cuts a day, a Monday week or a month — F6's counters, ceilings, alert, reports and counter rebuild, billing's minutes, tokens, plans, usage and promo codes. Hours stay UTC's: a whole-hour zone shares their boundaries, so the hour counters do not restart at the switch.
- Kept as it is: the renewal key `<subscription>:<expiry date>` is an idempotency key in the draft's form, not a total; moving its date could make a migrated attempt look new and charge twice.
- `usage_events` keeps two past months instead of one: its partitions are cut on UTC months, and the previous business month begins at 21:00 UTC on the last day of the UTC month two months back.
- At the switch, the day and month counters already filled keep the sums of their UTC period under the same label for the rest of that period; `shosai ai rebuild-spend-counters` recounts them from the cost rows with the new boundaries.
- The admin panel learns the zone from `GET /v1/admin/session` (`business_time_zone`); the account card, Plans and promo codes and AI models moved to "МСК" with the totals they show, Admin › Billing moves with its API.
- A totals boundary is not a person's day: a person's "today" in the cabinet follows their own zone, the business day follows Moscow, and the two are never mixed on one screen.

## Rejected

- **UTC for the server's totals** — clear for engineers, but the business reads the day in Moscow: a payment at 01:00 Moscow time would fall into "yesterday".
- **The operator's browser zone in the admin panel** — two operators in different cities would see different days for the same totals.
