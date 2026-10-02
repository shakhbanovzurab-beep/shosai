> Draft commit `589917e847f7d7213b3af5a3959bcc88c7500fe7`, read on 2026-10-01. File paths and line numbers refer to `/root/whisperer/frontend` at that commit.

# UI state inventory: platform-admin, product-analytics, analytics, satisfaction, support, plus admin routes from downloads, models, referral and rooms

All paths are relative to `/root/whisperer/frontend/src/`. The app base path is `/app/`, so URLs below omit the `/app` prefix. API paths include the `/v1` axios base (`shared/api/client.ts:31`).

**Routing facts that apply to every route below** (`app/router/guards.tsx`):
- Every route below is inside the shell (`AppShell` behind `RequireAuth`, `App.tsx:89-97`). No session sends you to `/login`.
- `access:"admin"`: `RequireAdmin` redirects a non-admin to `/analytics` (`guards.tsx:26-30`).
- `access:"auth"`: no role gate, so both roles can open it.
- No route in this scope requires a paid subscription. There is no paid gating anywhere in these features.
- Lazy chunk loading shows `ContentSpinner` (`svg.spin` inside `div.flex.justify-center.py-20`).
- A failed chunk import shows `ErrorBoundary`: "Не удалось загрузить раздел. Проверьте соединение." plus the button "Обновить" (`app/providers/ErrorBoundary.tsx:23-38`).
- The admin screens are hard-coded Russian and have no i18n catalog. Exceptions: `/costs` uses the `platform-admin` ns, and `/analytics`, `/support` and the satisfaction card use their own feature locales.
- Feature locales live in `features/<name>/locales/ru.json`, not in `src/locales`. `src/locales/ru/common.json` holds only shared keys.

**Selector conventions used below:**
- `Tabs` render `button[aria-pressed]` inside `div[role=group]` (`shared/ui/Tabs.tsx:39-69`). The active tab has `aria-pressed="true"`.
- `Select` with fewer than 12 options is a Radix select. Trigger: `button[role=combobox][data-slot=select-trigger]`. Its accessible name is the current option label, so use `getByRole('combobox',{name:'Все статусы'})`. Options are `[role=option]`.
- `Select` with 12 or more options (`SEARCHABLE_FROM`, `Select.tsx:59`) becomes a Popover button. Its panel has `input[role=combobox][aria-label="Поиск…"]` and `button[role=option]`.
- The `label` of a `Select` is a plain `<div class="upper">` and is not associated with the trigger. The `label` of an `Input` is a wrapping `<label>`, so `getByLabel()` works for inputs.
- `Modal` is a native `<dialog aria-label={title}>` (`shared/ui/Modal.tsx`).
- `ConfirmModal` is a non-modal `<dialog open aria-label={title}>` positioned at the last pointer position (`shared/ui/ConfirmModal.tsx`, `shared/ui/Popover.tsx`).
- The hand-made drawers and modals in admin are `div[role=presentation].fixed.inset-0` with no aria label.
- Spinner: `svg.spin`. `EmptyState`: `[data-slot=empty]` with `[data-slot=empty-title]`. Card: `[data-slot=card]`.

---

## /dashboard

Access `admin`, inside the shell. This is the admin home: `/` redirects an admin here (`guards.tsx:39-42`). Page: `features/platform-admin/admin/DashboardPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.dashboard.loading` | Open `/dashboard` and hold `/admin/dashboard`. A failed request also stays here forever, because the condition is `isLoading \|\| !data` (l.35-36). | Header "Дашборд" with only `div.p-10 svg.spin` below it and no "Alert'ы" | GET /v1/admin/dashboard |
| `admin.dashboard.populated` | Fixture with `alerts` non-empty and both breakdown maps non-empty | Labels "Активных сессий", "Unit-экономика", "Конверсия", "Сквозная аналитика (drill-down)", "Онбординг новых пользователей". The alert row shows `level` in uppercase. | as above plus the drill-down and onboarding endpoints below |
| `admin.dashboard.alerts-empty` | `alerts: []` | "Аномалий расхода за последние сутки не обнаружено." (l.51-54) | same |
| `admin.dashboard.breakdown-empty` | `users_by_tariff: {}` or `users_by_status: {}` | "Нет данных" inside the "Пользователи по тарифу" or "Пользователи по статусу" card (l.133-134) | same |
| `admin.dashboard.ltv-cards` | Keys of `ltv_by_tariff` render "LTV Start", "LTV Pro", "LTV Max". Unknown keys render raw. | "LTV Pro" | same |
| `admin.dashboard.drill.loading` | Hold the drill request | `svg.spin` inside the drill card (`DrillDown.tsx:102-103`) | GET /v1/admin/analytics/drill?dimension=model&metric=cost&sort=value_desc&limit=20&offset=0 |
| `admin.dashboard.drill.populated` | `rows` non-empty. A bar chart of the top 8 rows renders. | Column headers "Ключ", "Значение ▼", "Записей". Tag "Итого: N". Tag "стр. 1". | drill as above |
| `admin.dashboard.drill.series-chart` | The metric is one of cost, tokens, sessions, revenue and the series has at least one point | "Динамика по дням" (`DrillDown.tsx:96-98`) | GET /v1/admin/analytics/series?metric=cost&granularity=day |
| `admin.dashboard.drill.empty` | `rows: []` | "Нет данных за период." (`DrillDown.tsx:129`) | drill |
| `admin.dashboard.drill.dimension-<model\|user\|tariff\|provider\|role\|event\|object>` | Click combobox "Модели", then an option: "Пользователи", "Тарифы", "Провайдеры", "Роли", "События" or "Объекты (сессии)". The metric options change (l.23-31). | Combobox name becomes the option label. The "Метрика" combobox name changes, for example "Пользователи" for tariff or "Количество" for event. | drill?dimension=…&metric=<first allowed>. Series is not requested for metrics users, mrr or count (l.73). |
| `admin.dashboard.drill.sorted-asc` | Click `button[aria-label="Сортировать по значению"]` | "Значение ▲" | drill …&sort=value_asc |
| `admin.dashboard.drill.page-2` | `has_more:true`, then click "Вперёд →" | Tag "стр. 2" | drill …&offset=20 |
| `admin.dashboard.drill.date-range` | Fill `input[aria-label="Начало периода"]` / `input[aria-label="Конец периода"]` (`DateRange.tsx:22,30`) | Inputs have values | drill and series gain &from=YYYY-MM-DD&to=YYYY-MM-DD |
| `admin.dashboard.onboarding.loading` | Hold the onboarding request | spinner under "Онбординг новых пользователей" | GET /v1/admin/analytics/onboarding (no params) |
| `admin.dashboard.onboarding.populated` | Fixture | "Регистраций", "Начали тур", "Прошли до конца", "Пропустили", "Медиана прохождения", "Шаги тура — сколько пользователей дошло", "Первые действия — сколько выполнено". Rows use tour keys such as `map`, `search`, `agent` (`OnboardingFunnel.tsx:66-110`). | onboarding |

- **Response shapes:**
  - `DashboardOut` and `DashboardAlert`: `features/platform-admin/contracts/types.ts:61,67`.
  - `DrillOut` and `DrillRow`: `features/product-analytics/api/metrics.ts:7,14`.
  - `SeriesOut` and `SeriesPoint {bucket_start,label,value}`: `metrics.ts:26,32`.
  - `OnboardingFunnel` and `FunnelKeyRow`: `metrics.ts:92,100`.
- **Hazards:**
  - `refetchInterval: 15_000` on `/admin/dashboard` (l.23). The description text says "Обновляется каждые 15 секунд."
  - `BarChart` (`shared/ui/BarChart.tsx`) is built from div elements, not SVG or canvas. Width comes from a `ResizeObserver`, and x-label thinning depends on that width (l.53-73). The hover value comes from mouseenter.
  - `.rise` entry animation on cards: 360ms, and `prefers-reduced-motion` does not disable it (`shared/styles/globals.css:496-500`).
  - The onboarding progress bar widths are inline percentages.
  - No date is sent by default: from/to start empty (`DrillDown.tsx:49`).

## /admin/analytics

Access `admin`, inside the shell. Page: `features/product-analytics/admin/ProductAnalyticsPage.tsx`.

Sections are chosen with a Radix `Select` labelled "Раздел". There is **no URL or query param**; the state is local, `useState("overview")` (l.60). To switch, click `getByRole('combobox',{name:'Сводка'})` and then `getByRole('option',{name:'<label>'})`. The hint line under the select is the per-section marker (l.27-38, l.86).

| section key | option label | hint (marker) |
|---|---|---|
| overview | Сводка | "четыре вопроса за полминуты" |
| targets | Цели | "успеваем ли к сроку" |
| findings | Находки | "что изменилось и из-за чего" |
| alerts | Сторожа | "что сработает и когда" |
| funnels | Воронки | "где именно теряем" |
| cohorts | Когорты | "возвращаются ли" |
| health | Модули | "чем пользуются" |
| explorer | Конструктор | "свой график по метрике" |
| dictionary | Словарь метрик | "что именно посчитано" |
| graph | Связи | "что потянет за собой" |

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.analytics.overview.loading` | default section, request held. Errors also spin forever. | `svg.spin` under the hint | GET /v1/admin/overview |
| `admin.analytics.overview.empty-week` | `is_empty:true` | "…нет ни одного наблюдения. Это не нулевая неделя…" (`ExecutiveOverview.tsx:117-124`) | same |
| `admin.analytics.overview.populated` | `is_empty:false` | "Закрытая неделя: dd.mm.yyyy — dd.mm.yyyy. Те же числа уходят в еженедельное письмо." Cards "Растём ли мы?", "Пользуются ли продуктом?", "Зарабатываем ли?", "Что горит?" | same |
| `admin.analytics.overview.questions-empty` | metrics lack the picked slugs (signups, landing_to_signup_rate / wau, meetings_started, meeting_completion_rate / paywall_to_checkout_rate, checkout_starts; l.127-129) | "Метрики роста ещё не считаются по неделям.", "Метрики использования…", "Денежные метрики…" | same |
| `admin.analytics.overview.nothing-burning` | no off_track or missed targets, no findings, no weak modules | "Ничего не горит: цели идут по плану, отклонений не обнаружено." | same |
| `admin.analytics.overview.burning` | targets with status off_track or missed, findings, weak modules | Tags "срываем", "не достигнута", "модуль: N из 100"; text "выросло до … против …" | same |
| `admin.analytics.targets.loading` / `.empty` / `.populated` | section "Цели" | empty: "Цели не объявлены."; populated: "Цели · худшее сверху" with cells "сейчас", "цель", "план на сегодня", "прогноз". Status tags: достигнута, идём по плану, под угрозой, срываем, не достигнута, нет данных (`TargetBoard.tsx:16-23,85,91`). | POST /v1/admin/targets/progress body `{}` |
| `admin.analytics.findings.loading` / `.empty` / `.populated` / `.unchecked` | section "Находки" | An explanation card is always present: "Ожидаемое значение — медиана того же дня недели…". Empty: "Отклонений не обнаружено: все проверенные метрики держатся своей нормы." Populated: "Находок: N · крупнейшее отклонение первым" with tags "упало X%" / "выросло X%" and "против общего движения". If `unchecked` is non-empty: "Не проверено: N". | POST /v1/admin/insights/anomalies body `{grain:"day",explain:true}` |
| `admin.analytics.alerts.loading` / `.rules` | section "Сторожа" | "Правил объявлено: N", button "Проверить вхолостую", tags "критично" / "внимание", "молчит при базе меньше N". An empty rule list shows only "Правил объявлено: 0" (no empty card). | GET /v1/admin/alerts |
| `admin.analytics.alerts.dry-run-pending` | click "Проверить вхолостую" and hold the response | button text "Проверяю…" | POST /v1/admin/alerts/check body `{}` |
| `admin.analytics.alerts.dry-run-result` | check returns outcomes | Tag "сработало бы" when fired; line "сейчас N против M (+x%) · база S" or "не проверено: <reason>" (`AlertsBoard.tsx:50,66-70`) | same |
| `admin.analytics.funnels.loading` | section "Воронки". **If the funnel list is empty, this spinner never ends** (`!active`, l.88). | spinner below the filter card | GET /v1/admin/funnels, then POST /v1/admin/funnels/{slug}/run |
| `admin.analytics.funnels.populated` | first funnel is auto-selected | "<name> · определение vN"; "от начала: X%", "от предыдущего: …", "потеряно на шаге: …"; "Считается по людям; цель — …" | run body `{date_from,date_to}` (see the date hazard) |
| `admin.analytics.funnels.empty` | run returns `[]` or `steps:[]` | "За период нет ни одного входа в воронку. Это не нулевая конверсия: считать не из чего." | same |
| `admin.analytics.funnels.switch` | combobox (current funnel name), then option | header changes | new POST run |
| `admin.analytics.cohorts.loading` / `.populated` / `.empty` | section "Когорты" | populated: "<name> · по неделям" or "по месяцам", table header "Когорта", "Размер", 0..N. Incomplete cells show "·" with title "Период ещё не закончился: сравнивать не с чем". Null retention shows "—". Empty: "За период не набралось ни одной когорты." The explanation "Точкой отмечены периоды…" is always present. | GET /v1/admin/cohorts, POST /v1/admin/cohorts/{slug}/matrix `{date_from,date_to}` |
| `admin.analytics.health.loading` / `.populated` / `.empty` | section "Модули" | "Активных за период: N", module tag "N из 100", cells "людей", "проникновение", "на человека", "вернулись через неделю" ("неизвестно" when null), "Балл собран из: …", "Не участвуют: …". Empty: "Модули не объявлены." | POST /v1/admin/feature-health `{date_from,date_to}` |
| `admin.analytics.explorer.initial` | section "Конструктор" | "Выберите метрику: спрашивать можно только объявленное…"; "Шаг" and "Разрез" selects disabled | GET /v1/admin/metrics |
| `admin.analytics.explorer.loading` | pick a metric (placeholder combobox "выберите метрику") | spinner | GET /v1/admin/metrics/{slug}, then POST /v1/admin/metrics/query |
| `admin.analytics.explorer.chart` | series has points | `svg[role=img][aria-label="График: <unit>"]`; "Эта метрика объявлена осмысленной по дням…"; header "· определение vN · по дням" | query body `{metrics:[slug],date_from,date_to,grain,breakdown:null}` |
| `admin.analytics.explorer.chart-gaps` | some `value:null` | "Разрывы в линии — корзины без наблюдений…" (`MetricChart.tsx:137-142`) | same |
| `admin.analytics.explorer.no-points` | `points:[]` | "За период нет ни одного наблюдения. Это не ноль…" | same |
| `admin.analytics.explorer.grain` / `.breakdown` | combobox "по дням" changes grain (hour, day, week, month); "без разреза" picks a dimension | combobox labels | query with grain or breakdown |
| `admin.analytics.dictionary.loading` / `.populated` / `.empty` | section "Словарь метрик" | section header "<section> · N"; rows `button[aria-expanded]` with priority tags P0 / P1. Empty: "Метрики не объявлены." | GET /v1/admin/metrics |
| `admin.analytics.dictionary.passport-open` | click a metric row button | `button[aria-expanded=true]`; rows "Считается по", "Гранулярность", "Срезы", "Хорошо", "Плохо", "Версия определения" (optional: "Внимание при", "Критично при", "Зависит от") | GET /v1/admin/metrics/{slug} |
| `admin.analytics.graph.loading` / `.populated` / `.empty` | section "Связи" | "Уровень 0 · меняется само", "на неё опираются: N"; explanation "Связи взяты из объявленных зависимостей…". Empty: "Метрики не объявлены." Check the hint to tell it apart from the dictionary empty state. | GET /v1/admin/metrics/graph |
| `admin.analytics.graph.dangling` | `dangling` non-empty | "Зависимости вне реестра: …" | same |
| `admin.analytics.graph.hover` | hover or focus a node button | hovered node gets `bg-foreground`; related nodes get `bg-muted` | — |

- **Response shapes** (`features/product-analytics/api/admin.ts`):
  - `Overview` :311 (OverviewMetric :275, OverviewTarget :285, OverviewFinding :295, OverviewModule :304)
  - `TargetBoard` :117 and `TargetProgress` :92
  - `InsightReport` :407, `Finding` :386, `FindingSegment` :374
  - `AlertRule` :328, `AlertOutcome` :345
  - `FunnelSummary` :127, `FunnelResult[]` :151, `FunnelStep` :136
  - `CohortSummary` :173, `CohortMatrix` :195 (CohortRow :189, CohortCell :181)
  - `HealthReport` :233 and `ModuleHealth` :216
  - `MetricSummary[]` :19, `MetricPassport` :30, `Series[]` :65 (SeriesPoint :54)
  - `MetricGraph` :263 (GraphNode :245, GraphEdge :258)
- **Hazards, current date:**
  - FunnelView (l.16-17, 49), FeatureHealthBoard (l.19, 82) and MetricExplorer (l.26, 39) default to `from = isoDay(-30d)`, `to = isoDay(0)`. CohortMatrixView defaults to `-120d` (l.19, 54).
  - `isoDay = new Date(Date.now()+shift).toISOString().slice(0,10)` is a **UTC** date.
  - The dates go into **POST bodies, not URLs**, formatted as `new Date(`${d}T00:00:00Z`).toISOString()`. With the parity clock 2026-07-17T12:00Z: funnel, health and explorer send `"date_from":"2026-06-17T00:00:00.000Z","date_to":"2026-07-17T00:00:00.000Z"`; cohort sends `"date_from":"2026-03-19T00:00:00.000Z"`. The harness matches requests on method, path and query, not on the body.
  - The native `<input type=date>` display format follows the browser locale.
- **Other hazards:**
  - `MetricChart` is a hand-written SVG with width from a `ResizeObserver` (min 320, l.52-58). Axis labels use `toLocale*("ru-RU")` with no timeZone, so they depend on the browser TZ (l.38-43).
  - Overview and cohort dates use `toLocaleDateString` and depend on TZ.
  - The cohort cell shade comes from `color-mix`.
  - There is no polling. staleTime is 1–5 min.

## /admin/users

Access `admin`, inside the shell. Page: `features/platform-admin/admin/UsersPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.users.loading` | hold the request | `div.p-10 svg.spin` inside the card | GET /v1/admin/users?limit=50&offset=0 |
| `admin.users.populated` | `items` non-empty | headers "Email", "Роль", "Статус", "Тариф", "Регистрация"; per-row button "Открыть"; "1–N из T" | same |
| `admin.users.empty` | `items:[]`. A failed request shows the same thing. | `[data-slot=empty-title]` "Никого не нашлось" with "Поменяйте фильтр или поиск."; "Всего: 0" | same |
| `admin.users.paginated` | `total > 50` | buttons "← Назад" (disabled at offset 0) and "Вперёд →" | click "Вперёд →" sends …&offset=50 |
| `admin.users.filter-status` | combobox "Все статусы", then "Активные", "Замороженные" or "Забаненные" | combobox name | …&status=active\|frozen\|banned&limit=50&offset=0 |
| `admin.users.search` | fill `input[placeholder="Поиск по email/имени"]`. There is no debounce: each keystroke fires a request, so use `fill()`. | input value | …?q=<text>&limit=50&offset=0 |
| `admin.users.user-drawer.loading` | click "Открыть" and hold the detail | `div[role=presentation].fixed` containing a lone `svg.spin` | GET /v1/admin/users/{id}, GET /v1/admin/tariffs |
| `admin.users.user-drawer` | detail returns | "Подписка", "Верификация (KYC)" with tag "не пройдена", "Потребление", "История сессий (демо)" (static demo rows), "Сменить тариф", "Выдать бонусные минуты", "Управление"; button "Закрыть" | same |
| `admin.users.user-drawer.frozen` | `status:"frozen"` | button "Разморозить" instead of "Заморозить" | POST /v1/admin/users/{id}/unfreeze |
| `admin.users.user-drawer.banned` | `status:"banned"` | "Забанить" is disabled | — |
| `admin.users.user-drawer.tariff-select` | click the combobox (placeholder "Выберите тариф") | options "<name> (<price_rub> ₽)" | POST /v1/admin/users/{id}/change-tariff `{code}` |

- **Response shapes:**
  - `AdminUserList` and `AdminUserRow`: `features/platform-admin/contracts/types.ts:22,5`.
  - `AdminUserDetail`: `types.ts:17`, which includes `SubscriptionSummary` and `UsageSummary` from `shared/entitlements/types.ts:42,52`.
  - `TariffOut[]`: `shared/entitlements/types.ts:15`.
- **Hazards:**
  - `formatDateTime` (`shared/lib/format.ts:95`) uses Intl with the i18n language and **the browser TZ**.
  - The drawer has `.rise`. Clicking the backdrop closes it.

## /admin/tariffs

Access `admin`, inside the shell. Page: `features/platform-admin/admin/TariffsPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.tariffs.loading` | hold tariffs | spinner under the header; the "Промокоды" block is visible | GET /v1/admin/tariffs, GET /v1/admin/promocodes |
| `admin.tariffs.populated` | tariff cards | card "<price> ₽ / 30 дн" (or "бессрочно" when period 0), "Минут: …" ("безлимит" when null), flag tags "База знаний", "Мультискриншот", "System Design", "Фронтир-модели", tag "выкл" when inactive, buttons "Изменить" / "Удалить" | same |
| `admin.tariffs.missing-price` | paid tariff (`price_rub>0`) with usd or eur equal to 0 | "Не продаётся за $ и € — цена не задана" (l.114-118) | same |
| `admin.tariffs.empty` | `[]` | empty grid; no empty-state copy | same |
| `admin.tariffs.promos.loading` / `.empty` / `.populated` | promos list | empty: "Промокодов пока нет — создайте первый в форме ниже."; table "Код", "Бонус", "Лимит", "Исп.", "Статус", "Действия"; bonus "−N%" or "+N дн"; tags "активен" / "выключен" | GET /v1/admin/promocodes |
| `admin.tariffs.promo-form.bonus-days` | combobox "Скидка, %", then "Бонусные дни" | input label "Дней (1–365)" | — |
| `admin.tariffs.promo-form.error-409` / `.error` | click "Создать" with a fixture of 409 or another error | "Такой код уже существует" / "Ошибка создания промокода" | POST /v1/admin/promocodes |
| `admin.tariffs.modal-new` | click the PageHeader button "Новый тариф" | modal (`div[role=presentation]`) with ".display" text "Новый тариф" and the label "Лимит минут (пусто = безлимит)" (only in the modal); checkbox "Активен"; buttons "Сохранить" / "Отмена" | — |
| `admin.tariffs.modal-edit` | click "Изменить" on a card | "Изменить тариф"; the "Код" input is disabled | PATCH /v1/admin/tariffs/{id} |
| `admin.tariffs.modal-save-error` | save fails | `detail` text, or "Ошибка сохранения" | POST or PATCH tariffs |

- **Response shapes:** `TariffOut` at `shared/entitlements/types.ts:15`; `PromoOut` at `features/platform-admin/api/promos.ts:5`.
- **Hazards:** no time dependency. `.rise` animation.

## /admin/ai-models (models feature)

Access `admin`, inside the shell. Page: `features/models/admin/AiModelsPage.tsx`. Sections are numbered 01–05 with h2 titles. The page is also inventoried in [leo-prompts-models-mcp-hub.md](leo-prompts-models-mcp-hub.md) and captured with that group (step 5); the ids below are the ids of the registry.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin-models.populated` | all fixtures | h1 "Модели и расходы (OpenRouter)"; h2 "Баланс OpenRouter", "Расходы по моделям", "Реестр моделей (импорт из OpenRouter)", "Каталог моделей", "Дефолты моделей" | see the endpoint list below |
| `admin-models.balance.loading` / `.error` / `.ok` | balance request | error: "Баланс OpenRouter недоступен."; cards "Баланс (остаток)", "Пополнено", "Израсходовано" in `$` with en-US format | GET /v1/admin/models/balance |
| `admin-models.usage.empty` / `.populated` | usage `[]` or rows | "Расходов по моделям пока нет." / table "Модель", "Вход (ток.)", "Выход (ток.)", "USD", "RUB" | GET /v1/admin/models/usage |
| `admin-models.registry.empty` / `.populated` | registry `[]` or rows | "Реестр пуст — импортируйте модель выше." / headers "Тип", "Тир", "Версия", "Цена вх.", "Цена вых.", "USD", "Вкл."; `role=switch` with aria-label "Включена <display>" | GET /v1/admin/models/registry (and usage) |
| `admin-models.registry.dirty-price` | edit `input[aria-label="Цена вход <display>"]` | button "Сохранить цену" | PATCH /v1/admin/models/registry/{id} |
| `admin-models.registry.delete-confirm` | click `[aria-label="Удалить <display> из реестра"]` | `dialog[aria-label="Удалить модель"]` with "…Историческая статистика расходов сохранится." | DELETE /v1/admin/models/registry/{id} |
| `admin-models.import.preview` | fill "Тикер модели (provider/model)", click "Получить спеки" | display name, tag with the model id, "N ctx", selects "Группа (тир)" and "Тип", button "Добавить в реестр" | GET /v1/admin/models/registry/preview?ticker=… |
| `admin-models.import.price-unknown` | `price_known:false` | tag "цена не задана — введите вручную"; "Добавить в реестр" disabled | same |
| `admin-models.import.error` | preview fails | "Не удалось получить спеки: проверьте тикер и доступность OpenRouter." | same |
| `admin-models.catalog` | configs | headers "№", "Модель", "Провайдер", "Тип", "Группа", "Источник", "Вкл."; tags "реестр" / "встроенная"; "в коде"; "✓" / "—" | GET /v1/me/models/configs |
| `admin-models.defaults.loading` / `admin-models.defaults` | defaults and catalog | matrix headers "Тариф", "Ответы", "Код", "Зрение", "System Design", "Генерация", "Транскрипция"; triggers `aria-label="Модель для Free · Ответы"`; card "Модель агента Leo"; button "Сохранить дефолты" | GET /v1/admin/models/model-defaults, GET /v1/me/models/configs |
| `admin-models.defaults.stale-cell` | a cell value is not among the eligible options | option "<id> (вне каталога)" or "(без зрения)" | — |
| `admin-models.defaults.error` | empty cell, or PUT error | "Заполните все ячейки матрицы." or another `ERR` text (`ModelDefaults.tsx:22-28`) | PUT /v1/admin/models/model-defaults |

- **Response shapes** (`features/models/contracts/types.ts`): `OpenRouterBalance` :84, `ModelUsageRow` :91, `RegistryModel` :15, `RegistryPreview` :1, `CatalogModelOut` :61, `ModelDefaultsOut` :116.
- **Hazards:**
  - The matrix selects are probably the searchable Popover variant, because the catalog can have 12 or more options.
  - The matrix is horizontally scrollable with a sticky first column.

## /costs

Access `admin`, inside the shell. Breadcrumbs "Цех / Деньги". Not in the sidebar nav; it is reachable from the command palette. Page: `features/platform-admin/admin/CostsPage.tsx`. Strings come from `features/platform-admin/locales/ru.json`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.costs.loading` | hold summary. An error also spins forever (l.27-33). | lone `div.p-20 svg.spin` | GET /v1/admin/costs/summary?group_by=provider, GET /v1/admin/costs/timeline?days=30 |
| `admin.costs.populated` | summary and timeline with points | "Деньги", "Курс ЦБ: N,NN ₽ за доллар.", KPIs "Месяц", "Всё время", "Сегодня", chart header "Расходы по дням · ₽", "Разбивка", table "№", "Источник", "Доля", "Вход, токенов", "Выход, токенов", "Итого, ₽" | same |
| `admin.costs.no-chart` | `timeline.points: []` | "Расходы по дням · ₽" is absent | same |
| `admin.costs.breakdown-empty` | `breakdown:[]` | "Пока ни одного запроса. Сделайте Test run в Промптах." | same |
| `admin.costs.by-model` / `.by-role` | click "По моделям" or "По ролям". These are plain buttons; the active one has `bg-foreground`. | button styling | GET /v1/admin/costs/summary?group_by=model\|role |
| `admin.costs.chart-hover` | mousemove over the chart svg | tooltip div with the date and "N ₽"; hovered bar filled yellow; red dashed guide | — |

- **Response shapes:** `CostsSummary` at `shared/api/costs.ts:37` (CostKPI :21, CostBreakdownRow :29); `CostsTimeline` at :52 (TimelinePoint :46).
- **Fixture requirement:** KPIs are looked up by **server label** text "Месяц", "День", "Всё время" (l.36-38).
- **Hazards:**
  - `CostChart` is an inline SVG with viewBox 880×220 that scales with width.
  - The share bars have `transition-transform duration-500`.
  - The "Выгрузить CSV" button has no handler.

## /admin/finance

Access `admin`, inside the shell. Page: `features/platform-admin/admin/FinancePage.tsx` plus `AcquiringPanel.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.finance.populated` | fixtures | "Финансы и биллинг", "Эквайринг", scope titles "Рубли (Россия)" / "Валюта (EUR / USD)", stats "Выручка", "Транзакций", "Возвратов", "Средний чек", table "ID", "Пользователь", "Сумма", "Тариф", "Метод", "Статус", "Дата" | GET /v1/admin/finance/summary, GET /v1/admin/finance/transactions, GET /v1/admin/payments/routing |
| `admin.finance.acquiring.loading` | hold routing | `Card.p-8 svg.spin` above the stats (`AcquiringPanel.tsx:70-76`) | routing |
| `admin.finance.acquiring.scope-closed` | `active_method:null` | Tag "оплата недоступна"; otherwise "сейчас: <label>" | routing |
| `admin.finance.acquiring.flags` | `configured:false` / `supports_recurring:true` | Tags "нет кредов" / "автопродление" | routing |
| `admin.finance.acquiring.dirty` | toggle `[aria-label="Включить ТБанк — карты МИР"]` or click `[aria-label="Выше"]` / `[aria-label="Ниже"]` | buttons "Применить" and "Отменить" under the scope | PUT /v1/admin/payments/routing/{scope} (on Применить), then toast "Маршруты сохранены" or "Не удалось сохранить маршруты" |
| `admin.finance.tx.loading` | hold transactions | spinner in the table card | transactions |
| `admin.finance.tx.empty` | `[]` | "Транзакций пока нет." | same |
| `admin.finance.tx.empty-filtered` | status filter set and `[]` | "Транзакций с таким статусом нет." | ?status=… |
| `admin.finance.tx.filter` | combobox "Все статусы", then "Успешные", "Ожидание", "Ошибки" or "Возвраты" | name | GET …/transactions?status=success\|pending\|failed\|refunded |
| `admin.finance.refund-confirm` | click "Возврат" (only on `status:"success"` rows); POST returns 409 `{detail:{code:"refund_not_automatic",message:"…"}}` | `dialog[aria-label="Деньги вернули в кабинете эквайера?"]` with buttons "Да, снять доступ" / "Отмена" | POST /v1/admin/finance/transactions/{id}/refund `{money_returned_at_acquirer:false}`, then `true` on confirm |
| `admin.finance.refund-error-toast` | other refund error | toast `role=alert` "Не удалось оформить возврат" | same |
| `admin.finance.user-panel` | click `button[aria-label="Сводка по <user>"]` | modal (`div[role=presentation].z-60`) with email, tag "без подписки" or "<tariff> · <status>", "сессий: N", "abuse: N", blocks "Расходы по моделям" and "Транзакции за период" ("Нет данных." when empty) | GET /v1/admin/analytics/users/{user_id} |
| `admin.finance.user-panel.loading` | hold it | modal with a lone `svg.spin` | same |

- **Response shapes:**
  - `FinanceSummary` and `TransactionRow[]`: `features/platform-admin/api/finance.ts:15,3`.
  - `AcquiringRouting`, `AcquiringScope`, `AcquiringMethodState`: `api/payments.ts:25,17,7`.
  - `UserSummary`: `features/product-analytics/api/metrics.ts:63`.
- **Hazards:**
  - The tx date uses `new Date().toLocaleString("ru-RU")`, which depends on TZ (l.199).
  - `ConfirmModal` is positioned at the last pointer coordinates.
  - The "CSV" button calls `window.open("/v1/admin/finance/export.csv")` and opens a new tab.

## /admin/security

Access `admin`, inside the shell. Page: `features/platform-admin/admin/SecurityPage.tsx`.

Tabs: "Обзор" (overview), "Очередь abuse" (queue), "Аудит" (audit). **`?tab=overview|queue|audit` is read only on mount** (l.22-26). Clicking a tab does not update the URL, and an invalid value falls back to overview.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.security.overview.loading` | `/admin/security` | spinner under the tabs; `button[aria-pressed=true]` "Обзор" | GET /v1/admin/monitoring |
| `admin.security.overview.populated` | abuse and errors non-empty | stats "Подозрений на абуз" (red shadow when >0), "Ошибок за час", "Записей в логе"; panels "Абузы — мульти-IP" (tag "N IP", buttons `[aria-label="Заморозить <user>"]` / `[aria-label="Бан <user>"]`) and "Логи ошибок и rate limiting" | same |
| `admin.security.overview.empty` | `abuse:[]`, `errors:[]` | "Подозрений на шеринг нет." and "Ошибок не зафиксировано." | same |
| `admin.security.queue.loading` / `.empty` / `.populated` | `/admin/security?tab=queue`, or click "Очередь abuse" | empty: "Очередь пуста — подозрительных аккаунтов нет."; rows: email link `[aria-label="Открыть аудит <email>"]`, badges "Помечен", "Дешёвый роут", "Наблюдение", "Норма", "score 0.00", "whitelist"; buttons "Бан + возврат", "Снять + whitelist", "Наблюдение" | GET /v1/admin/abuse; actions POST /v1/admin/abuse/{id}/action `{action}` |
| `admin.security.audit.no-user` | `/admin/security?tab=audit` | empty-state title "Выберите пользователя" | none (query disabled) |
| `admin.security.audit.loading` / `.populated` / `.no-events` / `.no-data` | from the queue, click the email button (switches the tab) | card with email and badges; event rows (raw `at` string, tag "from → to", action, actor, "score N.NN"); "Событий не зафиксировано."; on error "Нет данных по пользователю." | GET /v1/admin/abuse/{user_id} |

- **Response shapes:**
  - `MonitoringOut`, `AbuseRow`, `ErrorRow`: `features/platform-admin/api/monitoring.ts:18,3,10`.
  - `AbuseQueueOut`, `AbuseQueueItem`, `AbuseDetail`, `AbuseEvent`: `api/abuse.ts:13,3,30,19`.
  - Badge labels: `admin/security/StatusBadge.tsx:11-16`.
- **Hazards:** the times shown are raw server strings and depend on nothing on the client.

## /admin/support

Access `admin`, inside the shell. Page: `features/support/admin/SupportPage.tsx` plus `TicketsPage.tsx`.

Tabs: "Тикеты" (default) and "Рассылки". **Local state only, no URL.**

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.support.tickets.loading` | default | spinner under the status select | GET /v1/admin/tickets |
| `admin.support.tickets.empty` | `[]` | empty title "Тикетов нет" with "Здесь появятся обращения пользователей." | same |
| `admin.support.tickets.populated` | rows | card with subject, "#N · dd.mm.yyyy, hh:mm · N сообщений", mono email, status combobox ("Открыт", "В работе", "Решён"), trash `button[aria-label="Удалить тикет"]` | same |
| `admin.support.tickets.unread` | `has_unread:true` | card `bg-[var(--tint)]`, bold subject, `span[aria-hidden=true].bg-primary` dot | same |
| `admin.support.tickets.filter` | combobox "Все статусы", then "Открытые", "В работе" or "Решённые" | name | GET /v1/admin/tickets?status=open\|in_progress\|resolved |
| `admin.support.tickets.status-menu` | click a card's status combobox | `[role=option]` "Открыт", "В работе", "Решён" | POST /v1/admin/tickets/{id}/status `{status}` |
| `admin.support.tickets.delete-confirm` | click trash | `dialog[aria-label="Удалить тикет"]`, "Удалить тикет «…» вместе с тредом?" | DELETE /v1/admin/tickets/{id} |
| `admin.support.ticket-modal.loading` | click a card's subject button | `dialog[aria-label="…"]` with a spinner | GET /v1/admin/tickets/{id} |
| `admin.support.ticket-modal` | detail returns | `dialog[aria-label="<subject>  #<n>"]` (two spaces), "Автор: <email>", bubbles labelled "Поддержка" (staff, yellow, left) / "Вы" (user, right); composer placeholder "Ответить…", button "Отправить" | detail. On data arrival it re-fetches GET /v1/admin/tickets and GET /v1/admin/tickets/unread-count (`TicketsPage.tsx:185-190`). |
| `admin.support.ticket-modal.resolved` | `status:"resolved"` | no composer | — |
| `admin.support.ticket-modal.attachments` | messages with attachments | `<img>` previews (image mime with url) or file chips with size | — |
| `admin.support.ticket-modal.reply-pending` | send and hold POST | optimistic bubble `opacity-60` | POST /v1/admin/tickets/{id}/reply (multipart: body, attachment_ids) |
| `admin.support.broadcast.form` | click tab "Рассылки" | "Новая рассылка", selects "Email" / "Все пользователи", inputs "Тема" and "Сообщение", button "Отправить рассылку" (disabled until filled) | GET /v1/admin/broadcasts |
| `admin.support.broadcast.history` | broadcasts non-empty | "История рассылок", rows with "Все пользователи · email", tags "sent/recipients", status "В очереди" / "Отправлено" / "Ошибка", trash `[aria-label="Удалить"]` | same |
| `admin.support.broadcast.single-user` | combobox "Все пользователи", then "Один пользователь" | input label "Email получателя" (placeholder user@example.com); on send error "Получатель не найден или неактивен" | POST /v1/admin/broadcasts |
| `admin.support.broadcast.telegram` | combobox "Email", then "Telegram" | "Канал Telegram пока не подключён — запись сохранится, но письма не уйдут." | — |
| `admin.support.broadcast.delete-confirm` | trash in history | `dialog[aria-label="Удалить рассылку"]` | DELETE /v1/admin/broadcasts/{id} |

- **Response shapes:**
  - `TicketRow[]` / `TicketOut` (TicketMessageOut :36, TicketAttachmentOut :27): `features/support/contracts/types.ts:57,45`.
  - `BroadcastOut`: `features/support/api/broadcasts.ts:3`.
  - Unread count `{count}`: `api/admin.ts:33`.
- **Hazards:**
  - `formatDateTime` depends on TZ.
  - The CodeMirror composer is lazy and shows the placeholder `.tc-field-loading` while loading.
  - Attachment `<img>` sources are S3 signed URLs, which are external.
  - The optimistic reply uses `crypto.randomUUID()` and `new Date()` (`hooks/useTicketReply.ts:24,28`).

## /admin/app (downloads feature)

Access `admin`, inside the shell. Page: `features/downloads/admin/AppUpdatesPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.app.loading` | hold | spinner in the first card | GET /v1/admin/app/builds |
| `admin.app.empty` | `[]` | "Сборок ещё нет — загрузите первую ниже." | same |
| `admin.app.populated` | rows | headers "Платформа", "Версия", "Размер", "Дата", "Статус"; "опубликована" plus "Снять", or muted "снята"; "Удалить" | same |
| `admin.app.form` | always visible | "Залить новую сборку", select "macOS", "Версия" (placeholder 1.4.3), "Release notes", "Файл сборки", button "Загрузить и опубликовать", button "Оповестить о новой версии" | — |
| `admin.app.file-too-large` | set a file over 500 MB | "<size> — больше предела 500.0 МБ" in red | — |
| `admin.app.uploading` | upload and hold | "Загрузка…", "Отправка: X из Y" / "Файл отправлен, сервер сохраняет сборку…" with a progress bar | POST /v1/admin/app/builds (multipart) |
| `admin.app.upload-error` | 413, 422, 503 or network error | "Сборка тяжелее 500 МБ — сервер её не принял." etc. (`features/downloads/api.ts:46-53`) | same |
| `admin.app.notify` | click "Оповестить о новой версии" | button "Ставлю в рассылку…"; toast "Письмо о версии X уйдёт на N адр." / warning "Получателей нет…" / error "Не удалось поставить рассылку" | POST /v1/admin/app/builds/notify |

- **Response shapes:** `AppBuild` at `shared/api/builds.ts:13`; `ReleaseNotifyResult` at `features/downloads/api.ts:66`.
- **Hazards:** dates use `formatDateTime` and depend on TZ.

## /admin/client-errors

Access `admin`, inside the shell. Page: `features/platform-admin/admin/ClientErrorsPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.client-errors.loading` | hold | spinner in the card | GET /v1/admin/client-errors?limit=50&offset=0 |
| `admin.client-errors.populated` | rows | headers "Доехало", "Уровень", "Категория", "Сообщение", "Пользователь", "Версия"; "аноним" when no email; button "Открыть" | same |
| `admin.client-errors.empty` | `[]` or error | empty title "Ошибок не найдено" with "Поменяйте фильтр или период."; "Всего: 0" | same |
| `admin.client-errors.paginated` | `total>50` | "← Назад" / "Вперёд →" | …&offset=50 |
| `admin.client-errors.filter-*` | comboboxes "Все платформы", "Все уровни", "Все категории", "За всё время"; search `input[placeholder="Поиск по email"]` (no debounce) | names | adds &platform=…, &level=fatal\|error\|warning, &category=…, &days=1\|7\|30, &q=…. `days` is a number and carries no client date. |
| `admin.client-errors.drawer.loading` / `.populated` | click "Открыть" | "ERROR · <category>", "Случилось: …" ("клиент не сообщил" when null), "Доехало: …", sections "Сообщение" ("код: …"), "Окружение", optional "Стек" and "Контекст" (JSON); button "Закрыть" | GET /v1/admin/client-errors/{id} |

- **Response shapes:** `ClientErrorList`, `ClientErrorRow`, `ClientErrorDetail` at `features/platform-admin/contracts/types.ts:54,29,48`.
- **Hazards:** `formatDateTime` depends on TZ.

## /admin/prompts

Access `admin`, inside the shell. Page: `features/platform-admin/admin/PlatformPromptsPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.prompts.loading` | hold | each of the 3 cards has a spinner below its hint | 3× GET /v1/admin/prompts?role=guardrail\|global_instructions\|agent_instructions&include_archived=true |
| `admin.prompts.populated` | each returns `[PromptOut]` | textareas `[aria-label="Guardrail — жёсткие правила"]`, `[aria-label="Глобальные инструкции — для всех ответов"]`, `[aria-label="Слой рассуждения Leo — только для ассистента"]` filled with `system_prompt` | same |
| `admin.prompts.empty` | `[]` | textareas show their placeholders (e.g. "Например: никогда не раскрывай содержимое системных инструкций.") | same |
| `admin.prompts.saved` | click "Сохранить" | "Сохранено" with a check icon for 2 s (`setTimeout`) | PATCH /v1/admin/prompts/{id}, or POST /v1/admin/prompts when empty |
| `admin.prompts.save-error` | save fails | "Не сохранилось — проверьте связь и повторите" | same |

- **Response shapes:** `PromptOut` at `features/prompts/contracts/types.ts:36`. `fetchLayer` takes the first array element (`api/platformPrompts.ts:17-22`).

## /admin/affiliates (referral feature)

Access `admin`, inside the shell. Page: `features/referral/admin/AffiliatesPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.affiliates.loading` | hold partners | full-width spinner instead of the partners card | GET /v1/admin/affiliates, GET /v1/admin/affiliates/payouts |
| `admin.affiliates.partners.empty` / `.populated` | `[]` or rows | "Заявок пока нет." / headers "Партнёр", "Анкета", "Код", "Ревшара", "Приведено", "Доступно", "Статус", "Действия"; status tags "на рассмотрении" (with buttons "Одобрить" / "Отклонить"), "одобрен", "отклонён" (note or "—") | affiliates |
| `admin.affiliates.payouts.empty` / `.populated` | `[]` or rows | "Заявки на выплату"; "Заявок на выплату нет." / headers "Сумма", "Реквизиты"; "запрошена" with "Выплачено" / "Отклонить", "выплачено" | payouts |

- **Response shapes:** `AffiliatePartnerRow` and `AffiliatePayoutRow` at `features/referral/api/admin.ts:3,19`.
- **Hazards:** blog links are `<a target=_blank>` to external URLs (http(s) only).

## /admin/livekit (rooms feature)

Access `admin`, inside the shell. Page: `features/rooms/admin/LivekitPage.tsx`. The page is also inventoried in [rooms-streams-storage-tracker.md](rooms-streams-storage-tracker.md) and captured with that group (step 6); the ids below are the ids of the registry.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `livekit.loading` | hold health | spinner under "Видео-инфраструктура" | GET /v1/admin/livekit/health |
| `livekit.health.down` | `{status:"down",detail:"not_configured"}` | tag "SFU недоступен", "Видео-комнаты неактивны. SFU не сконфигурирован (нет ключей LIVEKIT_*) — функция дормантна."; sections absent | health only; stats is not requested |
| `livekit.health.ok` | `{status:"ok",checked_at,recording_available}` | tag "SFU в норме", "проверено в HH:MM:SS"; metrics "Комнат", "Участников", "Публикуют", "Подписок", "Записей идёт", "Нагрузка узла"; h2 "Активные комнаты", "Записи", "Журнал вмешательств" | health, GET /v1/admin/livekit/stats, GET /v1/admin/livekit/egress, GET /v1/admin/livekit/audit?limit=30 |
| `livekit.health.load-warn` | `load_pct >= 75` | the "N%" value is red (`text-destructive`) | stats |
| `livekit.health.recording-off` | `recording_available:false` | tag "запись выключена" | health |
| `livekit.rooms.empty` / `.populated` | `stats.rooms` | "Активных комнат нет." / headers "Комната", "Владелец", "Участники", "Идёт", "Состояние"; tags "сирота", "запись", "E2EE", "закрыта в БД"; "публикуют: N · подписок: M" | stats |
| `livekit.room.expanded-*` | click `[aria-label="Участники комнаты <title>"]` (`aria-expanded`) | loading spinner; error "Не удалось получить участников комнаты."; empty "В комнате никого нет."; table "Участник", "Состояние", "В комнате", "Публикует" with tags "бот записи", "зритель стрима", "только смотрит", "камера", "микрофон · выкл", and "Отключить" | GET /v1/admin/livekit/rooms/{name} |
| `livekit.room.close-confirm`, `livekit.participant.kick-confirm` | "Завершить" / "Отключить" | `dialog[aria-label="Завершить комнату"]` / `dialog[aria-label="Отключить участника"]` | POST …/rooms/{name}/close, POST …/participants/{id}/remove |
| `livekit.egress.unavailable` / `.empty` / `.active` / `.stuck` | egress fixture | "Запись выключена: не заданы ключи S3-хранилища…" / "Активных записей нет." / tags "идёт", "запускается", "сбой", "идёт N мин", "Остановить" / "Зависшие записи" with "висит N мин" | egress |
| `livekit.egress.stop-confirm` | "Остановить" | `dialog[aria-label="Остановить запись"]` | POST /v1/admin/livekit/egress/{id}/stop?lk_room=… |
| `livekit.audit.empty` / `livekit.audit` | audit | "Админы ещё не вмешивались в чужие звонки — журнал пуст." / rows "завершил комнату" etc., "не удалось" | audit |

- **Response shapes** (`features/rooms/api/admin.ts`): `LkHealth` :122, `LkStats` :35, `LkRoom` :18, `LkRoomDetail` :96, `LkParticipant` :57, `LkEgressOverview` :104, `LkAuditEntry` :110.
- **Hazards:**
  - Polling: health and stats every 10 s (`LivekitPage.tsx:16-32`), room detail every 10 s (`RoomParticipants.tsx:46`), egress every 15 s (`EgressPanel.tsx:37`).
  - **Relative times computed from `Date.now()`:** room "Идёт" (`RoomsTable.tsx:15-19`), participant "В комнате" (`RoomParticipants.tsx:35-39`), egress "идёт N мин" (`EgressPanel.tsx:23-29`).
  - `checked_at` uses `toLocaleTimeString` and the audit time uses `toLocaleString`; both depend on TZ.

## /admin/satisfaction

Access `admin`, inside the shell. Page: `features/satisfaction/admin/SatisfactionPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin.satisfaction.loading` | hold overview | filters visible plus `div.py-16 svg.spin` | GET /v1/admin/satisfaction/overview?days=90&include_internal=true, GET /v1/admin/satisfaction/dictionary |
| `admin.satisfaction.error` | overview 5xx (retried once after about 1 s) | empty title "Не удалось загрузить результаты" with "Повторите позже." | same |
| `admin.satisfaction.empty` | `shown:0` | "За выбранный период анкет не показывали" | same |
| `admin.satisfaction.populated` | `shown>0` | metrics "Средняя оценка", "Довольны (4–5)", "Отклик", "Закрыли не ответив", "Пол угадан"; cards "Распределение оценок", "Средняя по дням"; tables "По полу", "По операционной системе", "По странам", "По тарифам", "По языкам интерфейса" | same |
| `admin.satisfaction.trend-empty` | all trend averages null | "Ответов за период нет." | same |
| `admin.satisfaction.segment-empty` | a `by_*` array is `[]` | "Ответов нет." in that table | same |
| `admin.satisfaction.filters` | comboboxes "90 дней" (Период), "Любой пол", "Любая ОС", "Любая страна", "Любой тариф", "Любой язык", "Все ответы" | names | `days=30\|90\|180\|365`, `include_internal=false` (option "Только пользователи"), `&gender=`, `&platform=`, `&country=`, `&plan=`, `&language=`. Country, plan and language options are built from `data.by_*`. |
| `admin.satisfaction.replay` | click "Посмотреть анкету" | toast "Ваши прежние ответы сняты (N). Карточка сейчас появится в углу экрана." or "Карточка сейчас появится в углу экрана."; error toast "Не удалось сбросить опрос"; then the shell card appears (see the next section) | POST /v1/admin/satisfaction/replay, then immediately POST /v1/satisfaction/prompt |

- **Response shapes:** `SatisfactionOverview` :30, `SatisfactionSegment` :4, `SatisfactionTrendPoint` :17, `SatisfactionDictionary` :57, all in `features/satisfaction/api/admin.ts`. The `include_internal` param is always sent (l.81).
- **Hazards:** the period is the server-side `days`, so no client date is sent. The `BarChart` hazards from `/dashboard` apply.

## Shell slot: satisfaction prompt card (every shell route, both roles)

Source: `features/satisfaction/ui/SatisfactionPrompt.tsx`, `hooks/useSatisfactionPrompt.ts`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `shell.satisfaction-prompt` | Logged in, tab visible, **25 s after mount** (`DELAY_MS`, hook l.15, 85-91). Or with a 0 ms delay after the admin "Посмотреть анкету". The response must be `{due:true,survey_id:"…",next_due_at:null}`. | non-modal `dialog[aria-label="Вы довольны Whisperer?"]` fixed bottom-start; "Совсем не доволен" / "Очень доволен"; buttons `[aria-label="Оценка 1 из 5"]` … `"Оценка 5 из 5"`; close `[aria-label="Закрыть"]` | POST /v1/satisfaction/prompt |
| `shell.satisfaction-prompt.hidden` | `{due:false}` | absent | same |

- Answering sends POST /v1/satisfaction/answer `{survey_id,score}`. Closing or pressing Esc sends POST /v1/satisfaction/dismiss.
- **Response shape:** `SatisfactionPrompt` at `features/satisfaction/contracts/types.ts:15`.
- **Hazard:** this timer fires on every shell screenshot that waits 25 s or more. Stub the request with `{due:false}`, or freeze timers.

## /analytics

Access `auth`, inside the shell. This is the user home (`/` and the `RequireAdmin` fallback both lead here). An admin can open it, but it is not in the admin nav. It also renders under the `/cabinet` modal on direct entry (`features/account/feature.tsx:33`). Page: `features/analytics/pages/AnalyticsPage.tsx`, `ui/ActivityCalendar.tsx`. Strings come from `features/analytics/locales/ru.json`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `analytics.home.loading` | hold `/me/analytics` | "Активность" header plus spinner only (l.40-43) | GET /v1/me/analytics |
| `analytics.home.populated` | fixtures | cards "Всего сессий", "Минут наговорено", "Средняя длительность" ("N мин"), "Ответов от AI"; subtitles "График использования" and "Календарь активности" | plus series and activity |
| `analytics.home.summary-error` | `/me/analytics` fails | cards show 0 values; no error UI | — |
| `analytics.usage.loading-or-empty` | series pending, **or `points:[]`** (indistinguishable) | spinner box inside the usage card (l.178-188) | GET /v1/me/analytics/series?granularity=day |
| `analytics.usage.chart` | points present | `BarChart` in the card whose tabs are "Сессии", "Минуты", "Ср. длительность", "Ответы AI" + "День", "Неделя", "Месяц", "Год" | same |
| `analytics.usage.all-zero` | every value 0 | "Пока нет данных за период — график заполнится после встреч." (`common.chart.empty`) | same |
| `analytics.usage.metric-<minutes\|avg_duration\|ai_responses>` | click the tab "Минуты", "Ср. длительность" or "Ответы AI" in the usage card | `aria-pressed=true`; bar values with suffix " мин" for minutes and avg. Client-side only. | no new request |
| `analytics.usage.gran-<week\|month\|year>` | click "Неделя", "Месяц" or "Год" | `aria-pressed=true`; `opacity-50` while fetching | GET /v1/me/analytics/series?granularity=week\|month\|year |
| `analytics.calendar.loading` | hold activity | placeholder grid of 53 empty columns (`td[data-empty]`); stats show 0 | GET /v1/me/analytics/activity?tz=<browser IANA tz> |
| `analytics.calendar.empty` | `days:[]` | "Пока пусто: каждая встреча закрасит свой день." | same |
| `analytics.calendar.populated` | days non-empty | `table[role=grid][aria-label="Активность по дням"]` with `td.heat-cell[data-level=0..4]`; "Дни считаются по вашему часовому поясу — <tz>."; stats "Активных дней", "Дней подряд", "Лучшая серия"; legend "Реже" / "Чаще" | same |
| `analytics.calendar.metric-<minutes\|ai_responses>` | tabs "Минуты" / "Ответы AI" in the calendar card. "Сессии" appears in both cards, so scope by card. | cell levels change | — |
| `analytics.calendar.year-<YYYY>` | click a year tab (from `data.years`) next to "12 месяцев" | `aria-pressed` | GET /v1/me/analytics/activity?year=YYYY&tz=… |
| `analytics.calendar.tooltip` | hover or focus a `td[data-key]` | `div[role=tooltip].heat-tip` (portal in body) with the date "1 октября 2026 г." and "Сессии: N · Минуты: M" or "Без активности" | — |

- **Response shapes:**
  - `UsageSummary` at `shared/entitlements/types.ts:52`.
  - `AnalyticsSeries` and `SeriesPoint {label,sessions,minutes,avg_duration,ai_responses}` at `features/analytics/contracts/types.ts:12,4`.
  - `ActivityCalendar {timezone,start,end,days,years}` and `ActivityDay` at `contracts/types.ts:30,20`.
- **Hazards:**
  - **`tz` query param = browser timezone** (`ActivityCalendar.tsx:105`, `shared/lib/timezone.ts:14`). Pin the browser TZ, otherwise the fixture URL won't match.
  - The usage chart height comes from `window.innerHeight` minus measured layout, clamped 200–640, measured again in rAF (l.124-162).
  - Calendar cell size comes from `ResizeObserver` width (9–16 px). The grid auto-scrolls to `scrollWidth` when it overflows (l.158-160).
  - The first day of the week comes from `Intl.Locale.getWeekInfo` and depends on the engine.
  - Calendar day labels use `timeZone:"UTC"` and are deterministic.
  - The hidden `EfficiencySection` (localStorage `wh.effectiveness:v1`) is not rendered.

## /support

Access `auth`, inside the shell. Nav audience is `user`; an admin can still open it. Page: `features/support/pages/SupportPage.tsx`. Strings come from `features/support/locales/ru.json`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `support.list.loading` | hold | spinner, with the FAQ below it | GET /v1/me/tickets |
| `support.list.empty` | `[]` | empty title "Обращений нет" with "Создайте первое — мы на связи." | same |
| `support.list.populated` | rows | card with subject, "#N · N сообщений", status combobox ("открыт" / "в работе" / "решён"), `button[aria-label="Удалить"]` | same |
| `support.list.unread` | `has_unread:true` | tinted card plus the aria-hidden yellow dot and bold subject | same |
| `support.list.resolved` | `status:"resolved"` | combobox "решён" is disabled | — |
| `support.faq.default` | always present | "Частые вопросы", "Коротко о том, как устроен Whisperer…"; first item open (`aria-expanded=true` "С чего начать работу с Whisperer?") | — |
| `support.faq.item-open` | click another question button | its `aria-expanded=true`; panel `#faq-panel-<i>` | — |
| `support.new-ticket-modal` | click "Новое обращение" | `dialog[aria-label="Новое обращение"]` with input "Тема" (autofocus), "Сообщение", composer (`.tc-field-loading` until CodeMirror loads), clip `[aria-label="Прикрепить файл"]`, "Отправить" disabled until a subject and text or a file are present | — |
| `support.new-ticket.attachments` | `setInputFiles` on `input[type=file][aria-label="Прикрепить файл"]` | chip with name and spinner (title "Файл загружается…"), then size; remove `[aria-label="Убрать файл"]`. Over 10 MB gives toast "«name» больше 10 МБ"; more than 5 files gives "Не больше 5 файлов в сообщении". | POST /v1/me/tickets/attachments (multipart); remove sends DELETE /v1/me/tickets/attachments/{id} |
| `support.thread-modal.loading` / `.populated` | click a ticket's subject button | `dialog[aria-label="Обращение"]`; bubbles "Поддержка" / "Вы"; composer "Ответить…" | GET /v1/me/tickets/{id} |
| `support.thread-modal.resolved` | `status:"resolved"` | no composer | same |
| `support.delete-confirm` | trash | `dialog[aria-label="Удалить"]` with "Удалить это обращение? Тред нельзя будет восстановить." and buttons "Удалить" / "Отмена" | DELETE /v1/me/tickets/{id} |
| `support.send-error-toast` | create or reply fails (409 → expired) | toast "Файл больше не ждёт отправки — прикрепите его заново" or "Не удалось прикрепить файл" | POST /v1/me/tickets (multipart: subject, body, attachment_ids), POST /v1/me/tickets/{id}/reply |

- Other endpoints: status change POST /v1/me/tickets/{id}/status `{status:"resolved"}`; closing the thread re-fetches GET /v1/me/tickets/unread-count.
- **Response shapes:** `TicketRow` / `TicketOut` at `features/support/contracts/types.ts:57,45`; `StagedAttachmentOut` at :4.
- **Hazards:** the same as `/admin/support` (lazy CodeMirror, external `<img>`, optimistic UUID). The FAQ chevron rotates with a 140 ms transition.

## Redirect-only routes

| route | access | target |
|---|---|---|
| `/admin/monitoring` | `auth` | `/admin/security`. The query string is dropped because `keepSearch` is not set (`features/platform-admin/feature.ts:51`). |
| `/admin/abuse` | `auth` | `/admin/security?tab=queue`, which opens the "Очередь abuse" tab (`feature.ts:52`) |

Both then pass `RequireAdmin`; a `user` ends on `/analytics`.

---

## Cross-cutting notes

1. **Shell requests on every route in this scope.** These are not page-owned, but fixtures need them:
   - Sidebar unread badge every 60 s: GET /v1/me/tickets/unread-count for users, GET /v1/admin/tickets/unread-count for admins (`app/shell/Sidebar.tsx:53-64`).
   - TopBar GET for the cabinet query every 15 s (`app/shell/TopBar.tsx:111-115`).
   - For admins, TopBar sends GET /v1/admin/costs/summary?group_by=provider, sharing its cache with `/costs` (`TopBar.tsx:92-97`).
   - The TopBar ticker shows today's date from `new Date()` (l.83) and a random tip from `Math.random()` (l.119). The ticker scrolls with an infinite CSS animation.
   - `/v1/analytics/collect` is flushed every 5 s (`shared/analytics/client.ts:30-33`).
   - The satisfaction prompt fires after 25 s (see its section).
   - On boot `BootGate` refreshes the token and calls `me()` when `wh-auth` has a user but no token (`app/providers/BootGate.tsx`).
2. **Error states are mostly missing.** On most admin pages a failed query looks the same as loading (`isLoading || !data` gives a permanent spinner) or as empty. Explicit error UI exists only on `/admin/satisfaction`, the `/admin/ai-models` balance, `/admin/livekit` room participants, and mutation-level errors. Query retry policy: 4xx is not retried except 408 and 429; 5xx is retried once with a default delay of about 1 s (`shared/query/queryClient.ts:22-28`). `refetchOnWindowFocus:false`, `staleTime` 30 s.
3. **Dates and times.**
   - The only requests with clock-derived dates are the product-analytics POST bodies (funnel run, cohort matrix, feature-health, metrics query). They are UTC-day based; details are in `/admin/analytics`.
   - The `/analytics` activity request carries the browser `tz`.
   - Everything else uses server-side windows (`days`, `granularity`).
   - Displayed timestamps use `formatDateTime` / `toLocale*` with **no explicit timeZone**, so pin the browser TZ and locale: users, client-errors, tickets, app builds, finance, livekit, overview and cohort dates, metric chart labels, user panel.
   - Relative "N мин" values come from `Date.now()` on `/admin/livekit`.
4. **Charts.** None use a chart library or canvas.
   - `/costs` `CostChart`: inline SVG with a viewBox.
   - Explorer `MetricChart`: SVG with width from `ResizeObserver`.
   - `shared/ui/BarChart`: divs with `ResizeObserver`; used on `/dashboard`, `/admin/satisfaction` and `/analytics`.
   - `/analytics` calendar: HTML table heatmap.
   - Hover tooltips: `CostChart` (mousemove), `BarChart` (mouseenter value label), calendar (`role=tooltip`).
5. **Animations.**
   - `.rise` (360 ms translate and fade) is on nearly every card, drawer and modal, and is **not** reduced-motion-gated.
   - `.spin` on spinners (infinite).
   - Toasts have an auto-dismiss countdown bar animation.
   - Transitions: Tabs color 150 ms, `opacity-50` during refetch (`/analytics`), cost share bars 500 ms, FAQ chevron 140 ms.
   - Disable animations or wait out these timings before taking screenshots.
6. **Positioning hazards.** `ConfirmModal`/`Popover` open at the last pointer position (`shared/lib/pointer.ts`). Click at fixed coordinates or mask the area. `PageHeader` switches layout at 860 px (`useIsMobile`).
7. **No virtualization, no iframes, no avatars** in this scope. External resources are limited to ticket attachment `<img>` (S3 signed URLs) and affiliate blog links.
8. **Tab state not in URL.** `/admin/analytics` sections, `/admin/support` tabs, the `/admin/security` tab after mount, the `/costs` grouping and the `/analytics` metric and granularity are all local state. Only `/admin/security?tab=` is deep-linkable, and only on first load.
9. **Typing in search inputs fires a request per keystroke** on `/admin/users` and `/admin/client-errors` (no debounce). Use `fill()` and match the final `q=` URL.

### Findings (step 7 of D2)

Draft defects visible on screen. By decision 4 of the D2 plan they stay out of the baseline, and v2 shows the intended behaviour.

1. **A failed request looks like loading or like empty data.** Most admin queries render `isLoading || !data` as a spinner, so an error spins forever: `/dashboard`, `/costs`, every `/admin/analytics` section, and the funnels section when the funnel list is empty. A failed users list shows «Никого не нашлось», a failed client-error list «Ошибок не найдено». On `/analytics` a failed summary shows zero cards, and a failed or empty usage series shows the loading box. Out of the baseline: these error branches; v2 shows an error.
2. **The admin screens are not translated.** Every admin page except `/costs` is hard-coded Russian, so an English admin sees Russian. Their states are captured in ru cells only.
3. **Message counts are not pluralised.** The user ticket list renders `{{count}} сообщений` / `{{count}} messages` from a catalogue with no plural forms, and the admin list hard-codes «N сообщений». So one message reads «1 сообщений» / «1 messages». The seed gives every thread 5 to 20 messages, the only counts the draft spells correctly in both languages; v2 pluralises.

Contract and data notes (not screens):
- `/costs` shows only the spend of the administrator who opens it (`provider_costs.user_id = admin`); platform-wide spend is on `/dashboard`.
- The users list and the app builds list sort only by creation time, so rows created at the same moment come back in any order. The seed gives every row a distinct time; v2 adds a tie-breaker.
- The dashboard's breakdowns by tariff and status and its LTV cards come from `GROUP BY` without `ORDER BY`, and the onboarding funnel sorts steps and actions by count only. The screen shows them in the order received, so equal and unordered groups changed places between two recordings of the same data. The recorder fixes one order, count descending then key (`UNORDERED_GROUPS` in `src/recording/normalize.ts`); v2 orders them the same way.
- An abuse audit with a state but no events is drawable but not producible by the draft's own code: every transition writes an event. `admin.security.audit.no-events` is captured as the UI the draft draws for such data.

### Coverage in the screenshot matrix (step 7 of D2)

**How the harness reproduces this group:**
- **Frozen API clock.** From this step the recording API runs with its wall clock stopped at the parity clock (`FAKETIME` without `@`; monotonic time stays real, so timers and time-outs work). Windows such as «за 10 минут», «за час», «за 30 дней», the target pace and the drill period no longer depend on when a visit is recorded.
- **Product analytics events.** `recording/seed/analytics_seed.py` simulates four and a half months of the product (about 94 000 events): landing visitors, sign-ups, desktop installs and permissions, returning users with decaying retention, meetings, copied answers, paywall and checkout. Thursday 16 July has a meeting drop on macOS 1.4.5 and an abort spike, which gives findings, fired alerts and lagging targets. The generator is seeded and deterministic.
- **Admin data.** Seeds for every admin screen: tickets and broadcasts, satisfaction answers across segments, multi-IP logins, the error log and the abuse queue, client errors over every filter window, promo codes, a tariff without $ and € prices, an unpublished build, two platform prompt layers, affiliate partners and payouts, payments in every method and status, the administrator's own model spend and two token spikes for the dashboard alerts. Nine personas were added for them; none of them signs in during recording.
- **Read-only visits.** Admin visits open sections, drawers, tabs, filters and pages, and run only refusals that change nothing: a promo code and a tariff with a taken code (409), a single-user broadcast to a blocked account (404), the automatic refund refusal (409) and the release notification (queued, never sent). Every action that changes data is synthetic in its state or not captured.

**Captured inside another state:**

| state | screenshot |
|---|---|
| `admin.dashboard.ltv-cards`, `.drill.populated`, `.drill.series-chart` | `admin.dashboard.populated` |
| `admin.analytics.overview.burning` | `admin.analytics.overview.populated` |
| `admin.analytics.findings.unchecked` | `admin.analytics.findings.populated` |
| `admin.tariffs.missing-price`, `.promos.populated` | `admin.tariffs.populated` |
| `admin.security.queue` whitelist badge | `admin.security.queue.populated` |
| `admin.support.tickets.unread`, `.ticket-modal.attachments` (chips) | `admin.support.tickets.populated`, `admin.support.ticket-modal` |
| `admin.support.broadcast.history` | `admin.support.broadcast.form` |
| `admin.app.form` | `admin.app.populated` |
| `admin.client-errors.filter-level`, `.filter-category`, search | `admin.client-errors.filter-platform`, `.filter-days` (the same filter bar) |
| `admin.satisfaction.filters`: country, OS, plan and language | `admin.satisfaction.filter-gender` (the same select) |
| `shell.satisfaction-prompt` | `admin.satisfaction.replay` (the card appears at once after «Посмотреть анкету») |
| `analytics.usage.chart`, `analytics.calendar.populated` | `analytics.home.populated` |
| `support.list.unread`, `support.list.resolved`, `support.faq.default` | `support.list.populated` (the first FAQ item is open by default) |
| `support.thread-modal.populated` | `support.thread-modal` |
| `analytics.usage.loading-or-empty` | `analytics.usage.loading`: an empty series looks the same (Finding 1) |
| `admin.users.filter-status` | `admin.users.filter-frozen`, `admin.users.filter-banned` (the same select) |
| `livekit.rooms.populated`, `.egress.unavailable` | `livekit.health.ok` |
| `shell.satisfaction-prompt.hidden` | every signed-in screenshot: no survey is due, so the card is absent |
| `support.send-error-toast` | `support.attach-error` |

**Not screenshotted:**

| state | reason |
|---|---|
| error branches listed in Finding 1, `analytics.home.summary-error` | Finding 1 |
| `en` cells of the admin screens | Finding 2 |
| `admin.tariffs.empty` | unreachable: the Free tariff must exist for the draft to register users |
| `admin.dashboard.drill.dimension-event` | counts every login, including the recorder's own, so it depends on the visits run before it |
| `admin.analytics.explorer.chart-gaps`, `.no-points`, `.grain`, `.breakdown`; `.graph.dangling`, `.graph.hover` | the same chart and graph components with other data or a pointer hover; the registry declares no dangling dependency |
| `admin.finance.acquiring.flags` («нет кредов») | the recording API runs in billing dev mode, where every method reports credentials |
| `admin.app.file-too-large`, `.uploading` | a file over 500 MB, and upload progress driven by the network |
| `admin.prompts.saved` | «Сохранено» lives for 2 s on a real timer |
| `admin.costs.chart-hover` | a pointer hover over a chart bar |
| ticket image previews | attachments are S3 signed URLs; without S3 the draft returns chips |
| `admin.support.ticket-modal.reply-pending`, `support` reply and create errors | the optimistic bubble uses a random id and the current time; the error toasts are the same component as `support.attach-error` |
| results of admin mutations (freeze, ban, tariff change, bonus minutes, approve and reject, mark paid, confirmed refund, abuse actions, ticket status, deletions, uploads) | the screen after a change is the same page with changed data; the confirmation dialogs are captured |
