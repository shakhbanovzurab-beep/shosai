# Upgrade API

The contract between the Upgrade page (`/app/upgrade`) and the FastAPI backend. The TypeScript
types in `src/features/upgrade/domain/contract.ts` are the source of truth (snake_case). The browser
calls `/api/billing/*`, which forwards to `${BACKEND_API_URL}/v1/billing/*` when set and otherwise
answers from an in-memory demo (`src/features/upgrade/server/`). Errors: `{"detail": "message"}`.

| Method | Path                     | Body                                                     | Response                      |
| ------ | ------------------------ | -------------------------------------------------------- | ----------------------------- |
| `GET`  | `/billing/plans`         | —                                                        | `PlansResponse`               |
| `POST` | `/billing/checkout`      | `{"plan_id": string, "seats"?: number}`                  | `{"url": string}`             |
| `POST` | `/billing/sales-inquiry` | `{"work_email", "company", "team_size", "message"}`      | `202 {"status": "received"}`  |

## Plans

Plans are managed in **Admin › Plans** (`/api/admin/plans`, `src/features/admin-plans`); the
catalog returned here is the active, non-archived plans in their `sort_order`, mapped to the
customer-facing shape (`id` is the plan's slug, `price` is the monthly price in the account's currency —
roubles for Russia, euros for the euro area and its neighbours, dollars elsewhere, chosen by the server from
the account's country, never the client — and `null` when the plan has `custom_pricing`). The account's own
plan is listed even when it is no longer on sale. The seeded plans:

| Tab        | Plan         | Price               | Users  | Meetings              | File Manager       | Knowledge for Leo  | Extras |
| ---------- | ------------ | ------------------- | ------ | --------------------- | ------------------ | ------------------ | ------ |
| Individual | Basic        | $0 / month          | 1      | 120 minutes per month | —                  | —                  | — |
| Individual | Professional | $15 / month         | 1      | unlimited             | 100 GB             | 100 MB             | — |
| Team       | Team         | $20 per user / month | 2–100 | unlimited             | 100 GB per user    | 100 MB per user    | shared workspace, member management, one invoice |
| Enterprise | Enterprise   | custom (sales)      | custom | unlimited             | from 250 GB        | from 1 GB          | everything in Team, SSO, security and admin controls, priority support, usage analytics |

Each plan has an `audience` (`individual`, `team`, `enterprise`: the tab it is shown on) and, for
team plans, `seats: {min, max}`; the price of a plan with `seats` is per user, and checkout takes the
number of users (`seats`, within the range; `422` otherwise).

`Entitlements` per plan: for a limit, `null` is unlimited and `0` means not included.
`knowledge_base_mb` is how much of the account's File Manager files Leo may use (the bytes of the
files marked "Use with Leo", see `file-manager-api.md`), in MB (`1024` is shown as "1 GB");
`file_manager_gb` is storage. On a custom-priced plan the storage limits are
the starting point of the negotiation and are shown as "from …".

### Workspace seats

A seat in a workspace on a team plan (see `workspace-api.md`) also covers the member's own tools.
`PlansResponse.seat` is `{workspace_name, plan_id}` for such a seat (the first one, when there are
several) and `null` otherwise; `effective_plan_id` is the plan whose limits apply in Personal: the
seat's plan when there is one, otherwise `current_plan_id`. The page says which workspace covers the
user; leaving that workspace returns them to their own plan.

### Enforcement

The backend enforces every limit, against the effective plan. The frontend only explains them:

- **File Manager** and **Knowledge** (`/app/file-manager/**`, `/app/knowledge-base`) show an
  upgrade screen instead of their content when the effective plan's limit is `0`.
- **Meetings** (`/app/meetings`) shows the month's minutes when the plan has an allowance. Once
  `usage.used_minutes` reaches `usage.limit_minutes`, Shosai stops capturing meetings until
  `usage.resets_at` (the first day of next month, UTC); the page, joining calls and past meetings
  with their notes stay available.
- If `GET /billing/plans` fails, the screens are shown as usual; the API still refuses what the plan
  doesn't include.

### Checkout and sales

- `POST /billing/checkout` takes the slug of a plan with a price and returns the acquirer's hosted
  payment page: TBank or CloudPayments for roubles, lava.top (cards or PayPal) for other currencies,
  as the platform's payment routes choose ([ADR 0054](../../docs/adr/0054-billing-plans-payments-trials-and-refunds.md)).
  A downgrade takes effect at the next renewal and needs no payment. Card details are never sent to this API. Errors: `404` unknown plan, `422` custom-priced plan, `409` the current
  plan. The demo has no provider and answers `501` with an explanation.
- A custom-priced plan has no checkout: the page sends a sales inquiry. `team_size` is one of
  `1-10`, `11-50`, `51-200`, `201-1000`, `1000+`; `message` may be empty (max 2000 characters),
  `company` max 120.
- **Settings › Billing** (`GET /settings/billing`, see `settings-api.md`) shows the same current
  plan; its `plan.id` is the plan's slug.
