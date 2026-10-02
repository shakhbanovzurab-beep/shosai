> Draft commit `589917e847f7d7213b3af5a3959bcc88c7500fe7`, read on 2026-10-01. File paths and line numbers refer to `/root/whisperer/frontend` at that commit.

# UI state inventory: auth, account, billing, referral, onboarding, downloads, hotkeys, app shell and cross-cutting UI

All paths are absolute under `/root/whisperer/frontend`. Line numbers are taken from the files as they are now. Russian text is quoted from the ru catalogs: `/root/whisperer/frontend/src/locales/ru/{common,auth,errors}.json` and `/root/whisperer/frontend/src/features/<f>/locales/ru.json`.

## Where the code differs from the brief

- **Captcha is Cloudflare Turnstile, not Yandex SmartCaptcha.** SmartCaptcha was removed on 07.09.2026 (`/root/whisperer/frontend/src/features/auth/model/captchaProvider.ts:6-9`).
  - Sitekey `0x4AAAAAAEG_5FH6bbYCUMRc` (:40); `CAPTCHA_ENABLED = true` (:45).
  - Loader: `https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=__whispererTurnstileReady` (`/root/whisperer/frontend/src/features/auth/model/turnstileLoader.ts:36-50`).
  - The SmartCaptcha comment in `/root/whisperer/frontend/index.html:26-28` is out of date.
- **No 2FA/TOTP exists.**
- **No cookie/consent banner, no PWA install prompt, no update-available banner.** A grep for `beforeinstallprompt`, `registerSW`, consent or update banners finds nothing. The only service worker is `/app/sw.js`, registered only by the Leo push flow when `localStorage["wh.push"]==="on"` and `Notification.permission==="granted"` (`/root/whisperer/frontend/src/shared/pwa/serviceWorker.ts:16,41`; `/root/whisperer/frontend/src/features/leo/hooks/usePushNotifications.ts:36,144-167`).
- **Billing has no routes** (`/root/whisperer/frontend/src/features/billing/feature.ts:16-21`). It renders only as the cabinet tabs «Подписка» and «Оплата».
- **Onboarding has no routes.** It is a `shell` slot (`/root/whisperer/frontend/src/features/onboarding/feature.ts:14-18`).
- **No root slots are declared.** The shell slots, in mount order, are: leo-chat, satisfaction-prompt, search-palette, onboarding-tour (registry order, `/root/whisperer/frontend/src/app/registry.ts:40-73`).
- **There is no SPA 404 page.** `*` hard-redirects to the landing `/404/` (`/root/whisperer/frontend/src/app/pages/NotFoundPage.tsx:25-43`).
- **`RequireAuth` passes if `accessToken || user`** (`/root/whisperer/frontend/src/app/router/guards.tsx:19-24`). It redirects to `/login` without carrying `next`.

---

## Boot sequence (surface `BootGate`, before the shell renders)

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `boot.i18n-pending` | Any load. `main.tsx` awaits `initI18n` before React mounts. | Empty `#root`; `html[data-theme]` already set by the inline script | `GET /v1/i18n/detect` (plain `fetch`, 1.5 s timeout), only if `wh.lang` is missing and `navigator.languages` has no supported language |
| `boot.spinner` | `localStorage["wh-auth"]` has `state.user`, no in-memory token; `POST /v1/auth/refresh` is pending or delayed | Full-screen centred `svg.spin` (`div.h-screen`), no sidebar | `POST /v1/auth/refresh` |
| `boot.refresh-dead` | refresh → 401, or 403 with no `meetassist_csrf` cookie | Ends on `/login` (store cleared) | same |
| `boot.refresh-network` | refresh aborted (no response) | App renders with the persisted user; the `/v1/health` probe starts and the overlay appears if it fails | `GET /v1/health` |

**Exact order for a signed-in user** (`/root/whisperer/frontend/src/app/main.tsx:17-53`, `/root/whisperer/frontend/src/app/providers/BootGate.tsx:22-77`, `/root/whisperer/frontend/src/shared/api/client.ts:134-232`):

1. Before any JS: the inline script in `index.html:60-102` reads `wh.theme` (default `light`), `wh.appearance` (font), and `wh.lang` (sets `html[lang]`, then `<link href="/fonts/roles-<lang>-<role>.css">`). Yandex Metrika loads from `index.html:9-18` (`mc.yandex.ru`, webvisor on).
2. `initGa4()` loads `https://www.googletagmanager.com/gtag/js?id=G-96C7VNXBHZ`. `initAnalytics()` starts product analytics.
3. `initI18n`:
   - Language chain: `wh.lang` → `navigator.languages` → `GET /v1/i18n/detect` → `en` (`/root/whisperer/frontend/src/shared/i18n/index.ts:34-57`).
   - Then it loads the boot namespaces `auth`, `common`, `errors` (JS chunks, not API).
   - Then `syncWithProfile(persisted user)`: if `user.language` is supported, it switches to it. If `user.language` is null and `wh.lang` is set, it sends `PATCH /v1/me/profile {language}` (:99-130).
4. React mounts. `Toaster`, `ConnectionOverlay` and `UploadCenter` mount above `BootGate` (`/root/whisperer/frontend/src/app/App.tsx:69-81`).
5. `BootGate`: `needsRefresh = !accessToken && !!user` (BootGate.tsx:40) → `FullScreenSpinner` → `ensureAccessToken()` → `POST /v1/auth/refresh`.
   - It uses raw axios with `withCredentials` and header `X-CSRF-Token` = cookie `meetassist_csrf`, falling back to the persisted `csrfToken`.
   - It runs under the Web Lock `wh-auth-refresh` and broadcasts on BroadcastChannel `wh-auth` (client.ts:112-191).
   - Response is `LoginResponse {access_token, token_type:"Bearer", expires_in, csrf_token?}` (`/root/whisperer/frontend/src/shared/auth/types.ts:71-76`).
   - A 403 is retried once if the CSRF cookie changed.
6. `ready` → routes render. Then, **non-blocking**, `GET /v1/auth/me` → `UserMe` (`types.ts:35-69`) replaces the persisted user (BootGate.tsx:57-72).
   - If `user.timezone` is null → `PATCH /v1/me/profile {timezone}` (BootGate.tsx:22-34).
   - If `user.appearance` differs → the font is applied (`/root/whisperer/frontend/src/shared/stores/themeStore.ts:124-128`).
7. `/` → `HomeRedirect` → `/analytics` (user) or `/dashboard` (admin) (guards.tsx:39-42).
8. The `AppShell` mounts the always-on widgets listed in the next table.

### Always-mounted shell calls (every signed-in page)

| caller | request | condition / cadence | response shape |
|---|---|---|---|
| Sidebar `useAppVersion` (`/root/whisperer/frontend/src/shared/appVersion.ts:32-49`) | `GET /v1/app/builds` | staleTime 5 min. Key `["public-builds"]` is shared with `/download` and the welcome modal. | `AppBuild[]` (`/root/whisperer/frontend/src/shared/api/builds.ts:13-25`). Fallback version `1.4.2` (appVersion.ts:11). |
| Sidebar unread badge (`/root/whisperer/frontend/src/app/shell/Sidebar.tsx:53-64`) | `GET /v1/me/tickets/unread-count` (user) or `GET /v1/admin/tickets/unread-count` (admin) | every 60 s | `{count:number}` (`/root/whisperer/frontend/src/features/support/api/tickets.ts:60-63`, `api/admin.ts:33-36`) |
| `OnboardingLauncher` + `OnboardingTour` (non-admin only) | `GET /v1/me/onboarding` | staleTime 60 s, no refetch on focus (`/root/whisperer/frontend/src/features/onboarding/hooks/useOnboarding.ts:26-38`) | `OnboardingProgress` (`/root/whisperer/frontend/src/features/onboarding/api.ts:11-20`) |
| TopBar ticker (`/root/whisperer/frontend/src/app/shell/TopBar.tsx:101-106`) | `GET /v1/ticker` | staleTime 30 min, `retry:false` | `TickerData {weather?:{city,temp_c,emoji}, holiday?:{name}, stats?:{meetings_total,users_total}}` (`/root/whisperer/frontend/src/shared/api/ticker.ts:6-16`) |
| TopBar minutes (TopBar.tsx:111-115) | `GET /v1/me` | **every 15 s**, for all roles | `CabinetOut {subscription, usage, quota}` (`/root/whisperer/frontend/src/features/billing/contracts/types.ts:21-25`; sub-types in `/root/whisperer/frontend/src/shared/entitlements/types.ts:15-66`) |
| TopBar exchange rate (TopBar.tsx:92-97) | `GET /v1/admin/costs/summary?group_by=provider` | admin only | `CostsSummary` (`/root/whisperer/frontend/src/shared/api/costs.ts:37-44`; `rate_used` string) |
| Leo chat widget (`/root/whisperer/frontend/src/features/leo/hooks/useUserEvents.ts:12-15,31-100`) | WebSocket `ws(s)://<host>/v1/ws/user`, subprotocols `["whisperer-bearer", <access_token>]` | Sends hello, then ping every 25 s; reconnect backoff 1.5 s → 30 s | frames `reminder.due` / `reminder.settled` |
| Satisfaction prompt (`/root/whisperer/frontend/src/features/satisfaction/hooks/useSatisfactionPrompt.ts:15,62-90`) | `POST /v1/satisfaction/prompt` | 25 s after mount while the tab is visible; all roles | `{due, survey_id, next_due_at}` (`/root/whisperer/frontend/src/features/satisfaction/contracts/types.ts:15-19`). Return `{due:false,...}` to suppress the card «Вы довольны Whisperer?». |
| Route warm-up `warmRoutes` (`/root/whisperer/frontend/src/app/shell/AppShell.tsx:37`, `/root/whisperer/frontend/src/app/router/prefetch.ts:53-122`) | Every route chunk, plus prefetch queries `GET /v1/admin/prompts` (no guard), `GET /v1/me/referral`, `GET /v1/admin/context` (only if paid) | idle-time, one per idle slot | errors are swallowed |
| Product analytics (`/root/whisperer/frontend/src/shared/analytics/client.ts:30,33,95-145`) | `POST /v1/analytics/collect` (`fetch`, or `sendBeacon` on unload) | 5 s flush timer when events are queued | — |
| Connection probe (`/root/whisperer/frontend/src/shared/stores/connectionStore.ts:11,55-68`) | `GET /v1/health` (`fetch`, `no-store`, 6 s timeout) | **only** after a network error or a browser `offline`/`online` event; not periodic | `res.ok` |

The page itself also calls its own endpoints. Home `/analytics` calls `GET /v1/me/analytics`, `/v1/me/analytics/series?granularity=…` and `/v1/me/analytics/activity?tz=<browser tz>` (`/root/whisperer/frontend/src/features/analytics/api.ts:7-31`).

### API error envelope

All error handling is in `/root/whisperer/frontend/src/shared/api/authErrors.ts` and `/root/whisperer/frontend/src/shared/api/client.ts`.

- **`detail` formats** (`authErrors.ts:14-21`):
  - FastAPI `{"detail": "<code or human string>"}`, or `{"detail": {"code": "...", "message": "..."}}` (the code is used).
  - Array `detail` (422 validation) yields no code.
- **Aliases** (:38-44):
  - "Invalid email or password" → `invalid_credentials`
  - "Email already registered" → `email_taken`
  - "Invalid or expired reset token" → `reset_token_invalid`
  - "Email not verified" → `email_not_verified`
  - "Account banned" → `account_banned`
  - Any string starting "Rate limit exceeded" → `rate_limited`
- **`apiErrorMessage` order** (:66-75):
  1. No response → «Соединение прервано».
  2. Known `errors:<code>` key → that text.
  3. 429 → «Слишком много запросов. Подождите минуту и попробуйте снова.»
  4. 422 → «Проверьте правильность введённых данных.»
  5. 5xx → «Ошибка сервера. Мы уже разбираемся — попробуйте позже.»
  6. Otherwise the caller's fallback key.
- **Interceptor** (`client.ts:234-279`):
  - Any non-`/auth/` request that gets 403 with detail `account_banned`, `account_frozen` or `account_disabled` → error toast `errors:<detail>` + session cleared + `/login`.
  - A 401 on a non-auth URL → one shared refresh, then the request is retried once.
  - A failed refresh with 401 → session cleared.
  - Network errors → connection probe.
- **Query defaults** (`/root/whisperer/frontend/src/shared/query/queryClient.ts`): no retry on 4xx (except 408 and 429), one retry otherwise, staleTime 30 s, no refetch on focus.

---

## `/login` (public, outside the shell, anonymous)

Manifest: `/root/whisperer/frontend/src/features/auth/feature.ts:22`. Page: `/root/whisperer/frontend/src/features/auth/pages/LoginPage.tsx`.

The form has 5 modes: login, register, forgot, verify, socialConsent (:57). **Errors are shown only as toasts.** `state.error` is set but never rendered inline.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `auth.login.default` | `/app/login`, no `wh-auth`; providers → `{providers:[],config:{},audience:{}}`; Turnstile stubbed | `h1` «Привет!», «Войдите в свою студию.», eyebrow «Раздел №00», links «Забыли пароль?» and «Нет аккаунта? Регистрация» | `GET /v1/auth/social/providers?language=ru`; `GET /v1/app/builds` (poster, desktop only) |
| `auth.login.poster` | viewport > 860 px | Dark left column: «Whisperer», «пульт · v1.4.2», «© 2026, WHISPERER», release date `DD.MM.YYYY` | `GET /v1/app/builds` |
| `auth.login.mobile` | viewport ≤ 860 px | No poster; single-column form (:598-602) | — |
| `auth.login.ready` | fill `input[type=email]` and `input[type=password]`, captcha token present | `button[type=submit]` «Войти» enabled (disabled rule :895-905) | — |
| `auth.login.password-revealed` | click `button[aria-label="Показать пароль"]` | aria-label becomes «Скрыть пароль», `aria-pressed=true` | — |
| `auth.login.submitting` | `POST /v1/auth/login` delayed | Button text «Заходим…» + `svg.spin` | `POST /v1/auth/login` |
| `auth.login.error-invalid` | login → 401 `{"detail":"Invalid email or password"}` | toast `[role=alert]` «Неверный email или пароль»; captcha remounts and the token is cleared (:464) | same |
| `auth.login.error-captcha` | 400 `{"detail":"captcha_failed"}` | «Не удалось пройти капчу — попробуйте ещё раз» | same |
| `auth.login.error-too-many` | **Unreachable.** The draft backend never returns `too_many_attempts` (checked in step 2 of D2); the frontend branch is dead. Not in the screenshot matrix. | «Слишком много попыток входа. Подождите немного и попробуйте снова.» | — |
| `auth.login.error-rate-limited` | 429 `{"error":"Rate limit exceeded: 5 per 1 minute"}` — slowapi's own handler, body under `error`, not `detail` (checked in step 2 of D2) | «Слишком много запросов. Подождите минуту и попробуйте снова.» | same |
| `auth.login.error-banned` | 403 `{"detail":"account_banned"}` (also `account_frozen`, `account_disabled`) | «Аккаунт заблокирован. Обратитесь в поддержку.» (frozen: «Аккаунт заморожен…», disabled: «Аккаунт отключён…») | same |
| `auth.login.error-validation` | 422 `{"detail":[…]}` | «Проверьте правильность введённых данных.» | same |
| `auth.login.error-server` | 500 | «Ошибка сервера. Мы уже разбираемся — попробуйте позже.» | same |
| `auth.login.error-generic` | 400 `{"detail":"zzz"}` | «Не вышло войти» | same |
| `auth.login.error-network` | `route.abort()` | «Соединение прервано»; plus the overlay if `/v1/health` also fails | same + `/v1/health` |
| `auth.login.unverified` | login → 403 `{"detail":"Email not verified"}`; resend-code → 200 | Switches to verify: `h1` «Почти всё», notice + info toast «Подтвердите email — мы отправили код на {email}» | `POST /v1/auth/login`, `POST /v1/auth/resend-code` |
| `auth.login.success` | login 200 `LoginResponse`, then `/auth/me` | Navigates to `?next` (if internal), else `/analytics` or `/dashboard` (:243-276) | `POST /v1/auth/login`, `GET /v1/auth/me` |
| `auth.login.redirect-authed` | persisted user + refresh 200 | Immediate `<Navigate>` (:579-581) | refresh |
| `auth.login.lang-menu` | click `button[aria-label="Язык"]` (top-right, shows `ru`) | Popup with 16 `button[aria-pressed]` endonyms, «Русский» active | none when anonymous |
| `auth.login.social-world` | providers `["google","github"]`, `config.google.client_id`, audience `world` | Divider «или» with no help icon; `a[href^="/v1/auth/social/github/start"]` «Войти через GitHub»; Google GSI iframe | providers |
| `auth.login.social-ru` | providers `["yandex","vk"]`, config `{yandex:{client_id,token_page_url}, vk:{app_id,redirect_url}}`, audience `ru` | «или» + help button whose `aria-label` starts «Вход через Google и GitHub недоступен…»; Yandex host `div[id]` 40 px high; VK One Tap | `GET /v1/auth/social/vk/prepare?language=ru` → `VKSetup` |
| `auth.login.social-tip-open` | hover, focus or click the help button | `[role=tooltip]` with the legal text | — |
| `auth.login.social-return-error` | `/app/login?social_error=social_state_invalid` | toast «Время на вход истекло. Начните заново.» Other codes: `social_login_cancelled` «Вход отменён.», `social_email_required`, `social_provider_disabled`, `social_provider_failed`, `account_unavailable`; unknown → «Не удалось войти через сервис. Попробуйте ещё раз или войдите по почте.». Query params are stripped (:182-223). | — |
| `auth.login.social-return-busy` | `/app/login?social=<ticket>`, complete pending | Submit disabled (`socialBusy`); no other visible change | `POST /v1/auth/social/complete` |
| `auth.login.social-return-failed` | complete → 401 | toast «Не удалось войти через сервис…» | same |
| `auth.social-consent.default` | `/app/login?social_consent=T&social_provider=yandex`; pending → `{provider,email}` | `h1` «Ещё один шаг», «Это ваш первый вход…», box «Аккаунт: ivan@ya.ru», «Продолжить» disabled | `GET /v1/auth/social/pending?ticket=T` |
| `auth.social-consent.checked` | click the first checkbox label | «Продолжить» enabled | — |
| `auth.social-consent.submitting` / `.error` | consent pending → «Создаём…»; 422 `{"detail":"consent_required"}` → toast «Не удалось войти через сервис…» | | `POST /v1/auth/social/consent` → `LoginResponse` |

## `/register` (public, outside the shell; also `/login?ref=CODE`)

Manifest: `feature.ts:24`. Register mode is triggered at `LoginPage.tsx:149-156`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `auth.register.default` | `/app/register` | `h1` «Знакомимся», «Создайте аккаунт — 60 минут бесплатно.», fields «Имя» (autofocus), «Email», «Пароль», two consent checkboxes («Я ознакомлен(а) с политикой, офертой и даю согласие на обработку персональных данных», «Я даю согласие на получение информационных рассылок»), «Зарегистрироваться» disabled, **no social buttons**, link «Уже есть аккаунт? Войти» | providers |
| `auth.register.pw-weak` / `pw-fair` / `pw-good` / `pw-strong` | password `abc` / `Abcdefgh` / `Abcdefg1` / `Abcdef1!` | Strength label «Слабый» / «Средний» / «Хороший» / «Надёжный»; unmet-rule chips «Не меньше 8 символов», «Строчные и прописные», «Хотя бы одна цифра», «Хотя бы один спецсимвол» (`/root/whisperer/frontend/src/features/auth/ui/PasswordStrength.tsx:17-23,69-84`) | — |
| `auth.register.ready` | name + email + password + first checkbox + captcha | Button enabled | — |
| `auth.register.error-email-invalid` | email `abc` (everything else valid) | toast «Введите корректный email.» (no request) | — |
| `auth.register.error-password-short` | password shorter than 8 | toast «Пароль должен быть не короче 8 символов.» | — |
| `auth.register.submitting` | register pending | «Создаём…» | `POST /v1/auth/register` |
| `auth.register.error-email-taken` | 400 `{"detail":"Email already registered"}` | «Этот email уже зарегистрирован» | same |
| `auth.register.error-generic` | 400 unknown | «Не вышло зарегистрироваться» | same |
| `auth.verify.default` | register 200 `{verification_required:true,email}` | `h1` «Почти всё», «Введите 6-значный код из письма…», notice «Мы отправили 6-значный код на {email}», input placeholder `000000`, «Отправить заново через 60 с» (counts down), «Подтвердить» disabled, «Назад ко входу» | `POST /v1/auth/register` |
| `auth.verify.code-entered` | type 6 digits | «Подтвердить» enabled | — |
| `auth.verify.submitting` | verify pending | «Проверяем…» | `POST /v1/auth/verify-email` |
| `auth.verify.error` | 400 `{"detail":"invalid_code"}` | «Неверный или истёкший код» (fallback «Не вышло подтвердить код») | same |
| `auth.verify.resend-ready` | advance clock 60 s | «Отправить код заново» | — |
| `auth.verify.resent` / `resend-failed` | resend 200 → «Новый код отправлен на {email}»; 400 → «Не вышло отправить код, попробуйте позже» | | `POST /v1/auth/resend-code` |
| `auth.forgot.default` | click «Забыли пароль?» | `h1` «Сброс», «Укажите email — пришлём ссылку для сброса пароля.», «Прислать ссылку», «Вспомнили? Войти», no captcha | — |
| `auth.forgot.sending` / `sent` | forgot pending → «Отправляем…»; 200 → button «Отправлено» disabled + success toast «Инструкции по восстановлению доступа отправлены на указанный адрес», returns to login after 4 s | | `POST /v1/auth/forgot-password` |
| `auth.forgot.error` | 500 → «Ошибка сервера…»; 400 → «Что-то пошло не так. Попробуйте ещё раз.» | | same |

### Captcha sub-states (login and register only)

Code: `/root/whisperer/frontend/src/features/auth/ui/Captcha.tsx`, `ui/Turnstile.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `auth.captcha.loading` | loader not yet resolved | Empty `div` with `min-height:65px`; submit disabled | external `challenges.cloudflare.com` |
| `auth.captcha.ready` / `solved` | real or stubbed `window.turnstile` | Iframe inside the container; token enables submit | — |
| `auth.captcha.dead` | abort `challenges.cloudflare.com` (onerror is immediate; otherwise a 9 s timeout; an 18 s safety deadline) | Box «Проверка не загрузилась», «Похоже, её блокирует сеть или расширение браузера…», button «Попробовать снова» | `POST /v1/client/errors` telemetry (`captchaTelemetry.ts:38-55`) |
| `auth.captcha.stalled` | widget rendered, no iframe within 6 s and no token for 45 s | Hint + «Попробовать снова» below the live widget | same |

To make the captcha deterministic, define `window.turnstile` with an init script; the loader then uses it directly (`turnstileLoader.ts`, `if (window.turnstile) return Promise.resolve(...)`):

```
{ render(el, p) { el.appendChild(document.createElement('iframe')); setTimeout(() => p.callback('t')); return 'w'; }, remove() {}, reset() {} }
```

**Endpoint shapes** (`/root/whisperer/frontend/src/features/auth/api.ts`):
- `login` :13 → `LoginResponse`; `register` :26 → `VerificationRequiredResponse`
- `verifyEmail` :63 → `LoginResponse`; `resendCode` :70; `forgotPassword` :74; `resetPassword` :78
- `socialProviders` :112 → `SocialShowcase` :101-110; `vkPrepare` :137 → `VKSetup` :121-127
- `completeWidgetToken` `POST /v1/auth/social/{provider}/widget-token` :160 → `WidgetLogin {session, consent_ticket}` :153-156
- `socialPending` :176; `socialConsent` :185; `completeSocial` :209
- GitHub start link `/v1/auth/social/github/start?language=…&next=…&ref=…` :221-228
- `UserMe` and `LoginResponse`: `/root/whisperer/frontend/src/shared/auth/types.ts:35-81`

**Hazards on `/login`:**
- The poster animates (rAF scroll, timers, Leo notes every 9–18 s). Seeded PRNG, and frozen under `prefers-reduced-motion` (`/root/whisperer/frontend/src/features/auth/ui/PosterScene.tsx:63-77,296-318`).
- `autoFocus` on email/name/code plus a yellow focus shadow.
- 60 s resend countdown.
- Toast countdown bars.
- External scripts: Turnstile, Google GSI `accounts.google.com/gsi/client`, Yandex `yastatic.net/s3/passport-sdk/autofill/v1/sdk-suggest-with-polyfills-latest.js`, VK ID (`@vkid/sdk` chunk plus its iframes), GA4, Metrika.
- Captcha and social widgets take the current theme.

## `/reset-password` (public, outside the shell)

Page: `/root/whisperer/frontend/src/features/auth/pages/ResetPasswordPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `auth.reset.no-token` | `/app/reset-password` | Title «Новый пароль» + red «Ссылка некорректна — токен отсутствует. Запросите сброс заново.» (:73-74) | — |
| `auth.reset.default` | `?token=abc` | Fields «Новый пароль» (autofocus) and «Повторите пароль»; «Сохранить пароль» disabled until both are filled | — |
| `auth.reset.error-short` | both fields `1234567`, submit | Inline red text under the 2nd field + toast «Пароль должен быть не короче 8 символов.» | — |
| `auth.reset.error-mismatch` | different values | «Пароли не совпадают.» | — |
| `auth.reset.saving` | request delayed | «Сохраняем…» | `POST /v1/auth/reset-password {token,password}` |
| `auth.reset.error-token` | 400 `{"detail":"Invalid or expired reset token"}` | «Ссылка сброса недействительна или истекла» (unknown 400 → «Ссылка недействительна или истекла.») | same |
| `auth.reset.done` | 200 | «Пароль обновлён. Перенаправляем на вход…» + toast; navigates to `/login` after 1.8 s (:55) | same |

## `/connect` (public, outside the shell; desktop client browser login)

Page: `/root/whisperer/frontend/src/features/auth/pages/DesktopConnectPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `auth.connect.anon` | `/app/connect?state=S`, no session | Large «Whisperer» wordmark, «Подключение приложения», «Войдите в аккаунт, чтобы подключить десктоп-клиент Whisperer.», button «Войти на сайте» → `/login?next=%2Fconnect%3Fstate%3DS` (:66-75) | — |
| `auth.connect.working` | session present, code request delayed | «Подключаем…», «Разрешите открытие Whisperer…», spinner | `POST /v1/auth/desktop/code` → `{code, expires_in}` (api.ts:8-11) |
| `auth.connect.done` | 200 | «Готово!», «Вернитесь в приложение Whisperer. Эту вкладку можно закрыть.», «Открыть приложение»; `location.href = whisperer://auth?code=…&state=…` | same |
| `auth.connect.error` | 500 | «Не удалось подключить», «Код входа не создан. Попробуйте ещё раз.», «Повторить» | same |

Hazards: custom-scheme navigation, and `window.close()` on `visibilitychange`. A login with `next=/connect…` does a full `location.assign('/app/connect…')` (LoginPage.tsx:254-268).

## Redirect-only routes and role-based redirects

- `/` (access `auth`, inside the shell) → `/analytics` (user) or `/dashboard` (admin) (`/root/whisperer/frontend/src/app/router/appManifest.ts:18`, guards.tsx:39-42). Anonymous → `/login`.
- **Role guards** (guards.tsx:26-37):
  - `admin` routes for a non-admin → `/analytics`.
  - `user` routes (`/cabinet`) for an admin → `/dashboard`.
  - `/referral`, `/download` and `/hotkeys` are `auth`, so admins can open them too.
- **Any inside-shell route without a session** → `/login` (replace, no `next`).
- **Live redirects:**
  - `/settings/mcp` → `/cabinet/mcp` (keeps the query string) (`/root/whisperer/frontend/src/features/mcp/feature.ts:28`)
  - `/rooms` → `/calendar`
  - `/meetings/live` and `/import` → `/meetings`
  - `/admin/monitoring` → `/admin/security`
  - `/admin/abuse` → `/admin/security?tab=queue`
- **Cabinet-internal redirects** (`/root/whisperer/frontend/src/features/account/pages/CabinetModal.tsx:76-93`):
  - `/cabinet?paid=…` → `/cabinet/subscription?paid=…`
  - Unknown tab → `/cabinet`
  - `leo` or `mcp` tab on Free → `/cabinet`
- **`*`** (public, outside the shell): a blank `div.h-screen[aria-hidden]`, then `location.replace('/404/?from=%2Fapp%2F…')` for ru, or `/<lang>/404/` for other languages (NotFoundPage.tsx:25-43). Per the comments, unknown first path segments are answered with a 404 by the server and never reach React.

---

## App shell (`AppShell` + `Sidebar` + `TopBar`, every route except auth/connect/404)

Code: `/root/whisperer/frontend/src/app/shell/AppShell.tsx`, `Sidebar.tsx`, `TopBar.tsx`, `navGroups.ts`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `shell.desktop-full` | viewport > 1024 px | `div[data-sidebar="full"]`, 260 px aside: logo «Whisperer» + «пульт · v{version}», search button «Что ищем?» + kbd «⌘K» (Mac) or «Ctrl K», nav groups, footer avatar + name + «Личный кабинет», logout `button[aria-label="Выйти"]` | shell set |
| `shell.desktop-rail` | click `button[aria-label="Свернуть меню"]` | `div[data-sidebar="rail"]` (66 px), icons only; expand button `aria-label="Раскрыть меню"`; search `title="Поиск (⌘K)"` (literal ⌘) | — |
| `shell.tablet` | 861–1024 px | Rail by default (AppShell.tsx:66-74) | — |
| `shell.mobile` | ≤ 860 px | `div[data-sidebar="drawer"]`, no aside. TopBar row 2: `button[aria-label="Открыть меню"]`, breadcrumbs (e.g. «СТУДИЯ»), avatar `a[aria-label="Личный кабинет"]` (hidden for admin) | — |
| `shell.mobile-drawer-open` | click «Открыть меню» | Scrim `button[aria-label="Закрыть меню"]` + fixed full sidebar | — |
| `shell.nav-active` | any route | Active nav item has yellow fill; numbers `01`…`14` | — |
| `shell.support-badge` | unread-count `{count:3}` (`>9` shows `9+`) | Dark badge on «Поддержка» | unread-count |
| `shell.hub-beta` | always (user) | Tag «Beta» on «Хаб» | — |
| `shell.admin` | `user.role="admin"` | «Администратор» footer link to `/dashboard`; admin groups; no onboarding launcher; ticker shows «Курс ЦБ · 92,50 ₽» | admin unread, costs summary |
| `shell.ticker` | always | `header .ticker` marquee. Items in order: date («среда, 1 октября»), weather («Москва +12°C ☀️»), «🎉 {holiday}», «На 16 языках · {n} встреч обработано», «Осталось {n} мин» (when the quota has a limit), random tip, «Сборка {version}», plus the rate for admin. The list is rendered twice for the loop. | ticker, `/v1/me` |
| `shell.theme-toggle` | Ctrl/Cmd+Shift+L inside the shell (AppShell.tsx:78-87) | `html[data-theme]` flips; `wh.theme` is written | — |

User nav (from the manifests):
- «Обзор»: 01 «Активность»
- «Работа»: 02 «Хаб» [Beta], 03 «Встречи», 04 «Календарь», 05 «Трекер», 06 «База знаний», 07 «Файлы»
- «Студия»: 08 «Контекст», 09 «Промпты», 10 «Модели»
- «Система»: 11 «Поддержка», 12 «Горячие клавиши»
- «Рост»: 13 «Рефералка»
- «Приложение»: 14 «Скачать»

Group order is set at navGroups.ts:21-29.

Hazards:
- `.ticker` runs `ticker 60s linear infinite` and pauses on hover; **it has no reduced-motion rule** (`/root/whisperer/frontend/src/shared/styles/globals.css:517-540`).
- The date is captured on mount (TopBar.tsx:83-87).
- The tip uses `Math.random` (TopBar.tsx:119-122).
- The avatar status dot has `.pulse-y` (infinite animation).
- Leo FAB `[data-onboarding="agent-fab"]` lives in the Leo feature.

## Command palette (shell slot `search-palette`)

Code: `/root/whisperer/frontend/src/features/search/ui/SearchPalette.tsx`, `ui/CommandPalette.tsx`, `hooks/useCommandPalette.ts`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `shell.palette.open` | Ctrl/Cmd+K, or click `[data-onboarding="sidebar-search"]` | `dialog[aria-label="Командное меню"]`, input placeholder «Введите команду или поиск…» (focused after 10 ms), static commands («Перейти в Промпты», …, «Переключить тему»), footer «Найдено: N» | — |
| `shell.palette.too-short` | type 1 character that matches no command | «Введите минимум 2 символа» | — |
| `shell.palette.searching` / `results` / `empty` | ≥ 2 characters (debounced 220 ms) | «Ищем…» / grouped hits / «По запросу «q» ничего не нашли. Попробуйте короче.» | `GET /v1/me/search?q=&per_domain=5&domains=…` → `GlobalSearchOut` (`/root/whisperer/frontend/src/features/search/contracts/types.ts:29-36`) |
| `shell.palette.kb-loading` / `kb-unavailable` | documents query pending, or it errors or lists `unavailable:["documents"]` | «Ищу в базе знаний…» / «База знаний не ответила — результаты из неё не показаны» | second `/v1/me/search` with `domains=documents` |

## Connection overlay (root, above `BootGate`)

Code: `/root/whisperer/frontend/src/app/shell/ConnectionOverlay.tsx`, `/root/whisperer/frontend/src/shared/stores/connectionStore.ts`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `shell.connection-lost` | `context.setOffline(true)` (shows immediately), or abort an API call while `/v1/health` fails | `dialog[aria-label="Проблемы с соединением"]`; header chip «Соединение» / «Нет сети»; `h1` «Проблемы с соединением»; «Пытаемся переподключиться автоматически — не перезагружайте страницу»; log «Журнал разрыва» «связь потеряна — в эфире тишина»; «Попытка 1» / «Повтор через N с»; game «Эфир» «Поймано: 0» | `GET /v1/health` with backoff 1, 2, 4, 8, 15 s |
| `shell.connection-probing` | while a probe is in flight | «Стучимся в сервер…», log line «стучимся в сервер…» | same |
| `shell.connection-retry-n` | after N failures | Log «проба N: сервер не ответил»; quip cycles (`attempt % 4`), e.g. «Чайник закипает быстрее, чем возвращается Wi-Fi» | same |
| `shell.connection-rebooting` | click `[aria-label="Постучать по роутеру"]` | «Перезагружаем роутер… Связь это не вернёт, но душу греет» for 900 ms | — |
| `shell.connection-easter-egg` | 5 router taps | «Постучали 5 раз. Роутер впечатлён, интернет — не очень» | — |
| `shell.connection-calm` | `prefers-reduced-motion: reduce` | «анимация выключена в настройках системы»; no packets | — |
| `shell.connection-restored` | health 200 or any API success | Overlay removed + success toast «Соединение восстановлено»; all queries invalidated | — |

Hazards:
- mm:ss elapsed timer (1 s).
- Countdown re-render every 250 ms.
- A packet spawns every 900 ms.
- `conn-*` CSS animations (`/root/whisperer/frontend/src/app/shell/connection/*.tsx`; globals.css:557-593).

## Toaster (root, portal)

Code: `/root/whisperer/frontend/src/shared/ui/Toaster.tsx`, `/root/whisperer/frontend/src/shared/stores/toast.ts:5-10`.

- `shell.toast.error`: `[role=alert]`, ✕ icon, 7 s.
- `shell.toast.warning`: `[role=alert]`, zap icon, 7 s.
- `shell.toast.success`: `[role=status]`, check icon, 4 s.
- `shell.toast.info`: `[role=status]`, bell icon, 5.5 s.
- `duration 0` keeps the toast until closed.
- Close button: `button[aria-label="Закрыть"]`.
- Max 4 toasts; identical text and variant are de-duplicated (`toastStore.ts:31-37`).
- Hazards: `toast-bar` countdown animation (paused on hover), slide-out animation, positioned fixed top-end.

## Error boundary and spinners

- **`route.error-fallback`**: each route has its own boundary (`/root/whisperer/frontend/src/app/router/buildRoutes.tsx:36-49`); the app-level one is at App.tsx:85.
  - Marker: «Не удалось загрузить раздел. Проверьте соединение.» + button «Обновить» (`/root/whisperer/frontend/src/app/providers/ErrorBoundary.tsx:12-28`). The sidebar stays visible.
  - Deterministic trigger: `GET /v1/me/hotkeys` → `{"hotkeys":{}}` makes `/hotkeys` throw.
  - Chunk-404 trigger: also set `sessionStorage["vite-preload-reload-ts"]=Date.now()`, otherwise `vite:preloadError` reloads the page (main.tsx:17-31).
- **`route.loading`**: inside the shell, `main[data-main-scroll] svg.spin`; outside the shell, a full-screen `svg.spin`.

## UploadCenter (root, portal; hidden unless uploads exist)

Code: `/root/whisperer/frontend/src/shared/uploads/UploadCenter.tsx`.

- Reached only by uploading in storage or meetings (other features).
- Marker: `aside[aria-label="Загрузка файлов"]`.
- States:
  - `uploads.busy`: «Загрузка {n}%»
  - `uploads.done`: «Все файлы загружены»
  - `uploads.collapsed`: «Развернуть» / «Свернуть»
  - `uploads.row-failed`: «Не удалось загрузить» + «Повторить»
  - `uploads.row-canceled`: «Отменено»
  - `uploads.menu`: `button[title="Меню загрузок"]` → «Отменить загрузки» / «Очистить список»
- Adds a `beforeunload` guard while busy.

---

## Onboarding (shell slot `onboarding-tour`; non-admin only; controlled by `GET /v1/me/onboarding`)

Contracts: `/root/whisperer/frontend/src/features/onboarding/contracts/steps.ts:44-120`. Runner: `hooks/useTourRunner.ts`. UI: `ui/*.tsx`.

**Autostart** runs once per session, and never while on `/cabinet` (useTourRunner.ts:75-95):
- `status:"new"` → welcome modal.
- `status:"active"` with a non-null `current_step` → the tour resumes **at that step** and navigates to its route.
- `completed`, `skipped`, or `active` with `current_step:null` → nothing.

**Deep-link to any step:** return `{status:"active", audio_status:"heard", version:1, current_step:"<key>", completed_steps:[], done_actions:[], started_at:"2026-01-01T00:00:00Z", completed_at:null}` and land on `/app/analytics`. Then mock `POST /v1/me/onboarding/progress` → the same object. The fixture to suppress onboarding completely is in the cross-cutting notes.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `onboarding.welcome` | `status:"new"` | `dialog[aria-label="Добро пожаловать в Whisperer"]`, «Примерно 10 мин · можно прервать в любой момент», «Послушать Leo · 7 мин» (ru only), «Не сейчас», «Пройти тур»; block «Следующий шаг: приложение» with a platform download button | onboarding, `GET /v1/app/builds` |
| `onboarding.welcome-later` | click «Не сейчас», Esc, or the scrim | Modal closes | `POST /v1/me/onboarding/skip`; `POST /v1/me/onboarding/audio {status:"declined"}` (ru) |
| `onboarding.tour.step-N` (N = 1…24, table below) | «Пройти тур», or deep-link | `dialog.onb-card` with text «Шаг N из 24» + step title; spotlight `.onb-spot` (`.onb-scrim-full` when there is no anchor); buttons «Пропустить тур», «Назад» (N>1), «Далее», or «Завершить» on N=24; ✕ `title="Продолжу позже"` | `POST /v1/me/onboarding/progress {current_step}` + the route's own APIs |
| `onboarding.tour.step-N.cta` | non-paid step with an action (or paid user) | Yellow button, e.g. «Открыть ассистента» | — |
| `onboarding.tour.step-N.paid-locked` | paid step and Free user | Tag «Платный тариф» + link «Посмотреть тарифы» (opens `/cabinet/subscription`) | — |
| `onboarding.tour.mobile-drawer` | ≤ 860 px, anchor starting `sidebar-` or `nav-` | Drawer is open under the spotlight | — |
| `onboarding.tour.later` / `skip` | ✕ / Esc / «Пропустить тур» | Card closes; skip sends `POST /v1/me/onboarding/skip` | |
| `onboarding.finish` | «Завершить» on step 24 | `dialog[aria-label="Готово — вы знаете платформу"]`, «Первые шаги», «d из t», checklist items or «Все первые шаги сделаны. Дальше платформа работает на вас.», «Пройти тур заново», «Начать работу» | `POST /v1/me/onboarding/complete` |
| `onboarding.launcher-resume` | `active` + `current_step` | Sidebar button «Продолжить обучение» (flag icon), under the search button | — |
| `onboarding.launcher-listen` | status not `new`, `audio_status:"new"`, ru, no unfinished tour | «Послушать Leo · 7 мин» (voice icon); with `localStorage["wh.onb.audio"]` > 0 it reads «Продолжить обучение» | — |
| `onboarding.launcher-checklist` | not new, `0 < done_actions(reachable) < total` | «Первые шаги · d/t» | — |
| `onboarding.checklist` | click that launcher | `dialog[aria-label="Первые шаги"]`, «Незавершённые пункты остаются здесь — можно вернуться к ним когда удобно.»; items `button.onb-item[data-done]`; Free gets «Платный тариф» on context and upload; total is 4 on Free, 6 when paid | — |
| `onboarding.audio.stop-N` (N = 1…30) | «Послушать Leo» | `dialog.onb-card[aria-label="Leo показывает"]`, «Шаг N из 30», subtitle words, pause `title="Пауза"` / «Продолжить», «Повторить», «Продолжу позже», «Далее» | mp3 `/app/onboarding/ru/<id>.mp3` |
| `onboarding.audio.silent` | mp3 404 or autoplay blocked | All subtitle words visible; no pause button | — |
| `onboarding.audio.done` | after the last stop | «Подробный тур» / «За работу» | `POST /v1/me/onboarding/audio {status:"heard"}` |
| `onboarding.restart` | Cabinet → Общие → «Пройти заново» | Navigates to `/analytics`, tour at step 1 | `POST /v1/me/onboarding/restart` |

Tour steps (key → route → anchor `[data-onboarding=…]` → title; `*` marks paid):

| N | key | route | anchor | title | notes |
|---|---|---|---|---|---|
| 1 | map | `/analytics` | `sidebar-nav` | «Карта платформы» | |
| 2 | search | stays on current route | `sidebar-search` | «Глобальный поиск» | |
| 3 | agent | stays on current route | `agent-fab` | «Leo — ассистент платформы» | CTA «Открыть ассистента» |
| 4 | analytics | `/analytics` | `page-header` | «Активность — ваша домашняя страница» | |
| 5 | hub | `/hub` | `nav-hub` | «Хаб — место, где всё сходится» | |
| 6 | meetings | `/meetings` | `nav-meetings` | «Встречи и стенограммы» | |
| 7 | audio-upload | `/meetings` | `meetings-upload` | «Загрузка записи — не только для встреч» | |
| 8* | integrations | `/settings/integrations` | `meetings-nav` | «Интеграции» | |
| 9 | calendar | `/calendar` | `calendar-meet` | «Календарь и видеовстречи» | CTA «Создать встречу» |
| 10* | stream | `/calendar` | `calendar-stream` | «Стрим — вещание на зал» | |
| 11 | tracker | `/tracker` | `nav-tracker` | «Трекер задач» | |
| 12* | kb | `/knowledge-base` | `page-header` | «База знаний» | |
| 13* | storage | `/storage` | `storage-upload` | «Хранилище файлов» | CTA «Загрузить файл» |
| 14* | context | `/context` | `context-editor` | «Контекст о вас» | CTA «Заполнить контекст» |
| 15 | prompts | `/prompts` | `prompts-create` | «Промпты — характер ассистента» | CTA «Создать промпт» |
| 16* | skills | `/prompts` | `prompts-skills` | «Скиллы — готовые умения для промптов» | |
| 17 | models | `/models` | `page-header` | «Модели» | |
| 18 | support | `/support` | `nav-support` | «Поддержка» | |
| 19 | hotkeys | `/hotkeys` | `page-header` | «Горячие клавиши» | |
| 20 | referral | `/referral` | `nav-referral` | «Приглашения и бонусы» | |
| 21 | download | `/download` | `download-builds` | «Приложение для компьютера» | CTA «Скачать приложение» |
| 22 | cabinet | stays on current route | `sidebar-profile` | «Личный кабинет» | |
| 23* | leo | `/cabinet/leo` | `cabinet-tab-leo` | «Настройки Leo» | On Free the cabinet redirects to «Общие»: anchor missing, so full scrim + centred card |
| 24* | mcp | `/cabinet/mcp` | `cabinet-tab-mcp` | «Подключение к Claude и ChatGPT» | same as 23 |

Use «Шаг N из 24» plus the class `.onb-card` as the marker, because several titles equal page titles.

Audio stops (30, `/root/whisperer/frontend/src/features/onboarding/contracts/audio/ru.json`): door, leo, search, activity, hub, meetings, upload, integrations, calendar, stream, tracker, kb, storage, context, prompts, skills, models, support, hotkeys, referral, download, cabinet, cab-general, cab-profile, cab-leo, cab-mcp, cab-subscription, cab-billing, cab-data, end. Total 447.7 s → «7 мин».

**Endpoint shapes:**
- `OnboardingProgress`: `/root/whisperer/frontend/src/features/onboarding/api.ts:11-20`.
- `GET /v1/me/onboarding` :22; `POST /v1/me/onboarding/progress {current_step?|done_action?}` :28; `/audio` :37; `/complete` :42; `/skip` :47; `/restart` :52.
- `markOnboardingAction` (`useOnboarding.ts:82-97`) is also called from the `/download` build links and the welcome download button.

**Hazards:**
- Spotlight and card track the anchor every rAF and use smooth `scrollIntoView` (instant under reduced motion) (`hooks/useAnchorBox.ts`).
- The portal targets the open modal dialog (`model/portalHost.ts`).
- The audio card reveals subtitle words by playback time.
- The welcome download button depends on `navigator.platform` / UA: «Скачать для Mac» / «Скачать для Windows» / «Скачать для Linux» / the mobile note / «Приложений для вашей системы пока нет.» (`/root/whisperer/frontend/src/shared/ui/DesktopDownload.tsx:62-117`). **Headless Linux Chromium resolves to `linux`.**

---

## `/cabinet/:tab?` (access `user`; Free or paid; admin is redirected to `/dashboard`)

There are two declarations of the same path (`/root/whisperer/frontend/src/features/account/feature.tsx:23-46`):
- **Direct route inside the shell**: `/app/cabinet[/tab]` renders `AnalyticsPage` underneath plus the modal, so the analytics APIs are needed.
- **Modal route**: when opened from the UI with `state.backgroundLocation`, the current page stays underneath.

Openers: `a[data-onboarding="sidebar-profile"]` (desktop) or `a[aria-label="Личный кабинет"]` (mobile). Every paywall button «Перейти к тарифам» opens `/cabinet/subscription`.

Dialog: `dialog[aria-label="Личный кабинет"]`, `h2` «Личный кабинет». Close with the ✕ or scrim `button[aria-label="Закрыть"]`, or Esc. Tabs are `button[data-onboarding="cabinet-tab-<key>"][aria-pressed]`: «Общие», «Профиль», «Leo»*, «MCP»*, «Подписка», «Оплата», «Данные» (* hidden on Free; `/root/whisperer/frontend/src/features/account/contracts/tabs.ts:22-56`).

Layout: desktop card `min(1000px,94vw)` × 88 vh; mobile full-screen with the tab list above the content (CabinetModal.tsx:128-131; `/root/whisperer/frontend/src/features/account/ui/CabinetSettings.tsx:135,426-431`).

Always called while the cabinet is open: `GET /v1/me` (every 15 s) and `GET /v1/me/referral` (bonus) (CabinetSettings.tsx:81-89).

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `account.cabinet.loading` | first open, chunk loading | Direct route: content `svg.spin`. Modal: may flash the **full-screen** spinner (App-level Suspense, App.tsx:86). | — |
| `account.cabinet.general` | `/app/cabinet` | Section «Внешний вид» with hint «Тема действует в этом браузере…»; tiles «Светлая» / «Тёмная» / «Система» (`aria-pressed`); «Шрифт» tiles Whisperer / Sans / Serif / Native / Mono with sample «Аа Бб»; row «Язык» showing «Русский»; «Часовой пояс» with local time `HH:MM` + combobox; «Рассылки» switch `[role=switch][aria-label="Получать информационные рассылки"]`; «Обучение» «Пройти заново» | `/v1/me`, `/v1/me/referral` |
| `account.cabinet.general.theme-dark` / `theme-system` | click «Тёмная» / «Система» | `html[data-theme=dark]`; `wh.theme` | — |
| `account.cabinet.general.font-serif` (and the other roles) | click a tile | `html[data-font=serif]` (attribute removed for Whisperer) | `PATCH /v1/me/profile {appearance:{font}}`; error toast «Не удалось сохранить настройку. Она действует только на этом устройстве.» |
| `account.cabinet.general.lang-menu` | click `button[aria-label="Язык"]` | 16-item list | `PATCH /v1/me/profile {language}` on pick |
| `account.cabinet.general.tz-open` | click the button «Часовой пояс» (a `button`, not a combobox — checked in step 3 of D2) | listbox + search `aria-label="Поиск…"` | `PATCH /v1/me/profile {timezone}`; error «Не удалось сохранить часовой пояс» |
| `account.cabinet.general.marketing-on` / `marketing-off` | `user.marketing_consent` | switch `aria-checked` | `PATCH …{marketing_consent}`; error «Не удалось сохранить настройку рассылок» |
| `account.cabinet.profile` | `/app/cabinet/profile` | «Профиль», avatar initial, name or «Как к вам обращаться», email, «Сменить аватар», inputs «Имя» / «Email» (disabled), status «Изменения сохраняются автоматически», danger row «Удалить аккаунт», row «Выход из аккаунта» + «Выйти» | — |
| `account.cabinet.profile.saving` / `saved` | type a name, wait 700 ms | «Сохранение…» → «✓ Изменения сохранены» | `PATCH /v1/me/profile {username}` → `GET /v1/auth/me` |
| `account.cabinet.profile.avatar-uploading` / `avatar-error` | pick a file; upload pending or 413 | «Загрузка…» / «Не удалось загрузить. PNG/JPEG/WEBP/GIF до 512 КБ.» | `POST /v1/me/avatar` (multipart) → `{avatar_url}` |
| `account.cabinet.profile.delete-confirm` | click «Удалить аккаунт» | `dialog[aria-label="Удалить аккаунт"]`, warning text, input «Наберите {email}, чтобы подтвердить», «Отмена», danger button disabled until the email matches | — |
| `account.cabinet.profile.delete-error` / `delete-success` | DELETE → 500: toast «Не удалось удалить аккаунт.»; 200: `wh-auth` cleared and `location.replace('/app/login')` | | `DELETE /v1/me/data/account {confirm_email}` |
| `account.cabinet.profile.logout` | «Выйти» | full reload to `/app/login` | `POST /v1/auth/logout` |
| `account.cabinet.leo` | paid user, `/cabinet/leo` | Leo blocks (personalisation, connectors, initiative, memory, errands, capabilities). APIs belong to the Leo feature. | features/leo |
| `account.cabinet.mcp` | paid user, `/cabinet/mcp` | Segmented toggle «Сервер» / «Клиент» + hint. APIs belong to the MCP feature. | features/mcp |
| `account.cabinet.subscription` / `billing` | see the Billing section below | | |
| `account.cabinet.data` | `/cabinet/data` | «Приватность»: switches `aria-label="Включить режим no-logs"` and «Заводить задачи из встреч автоматически»; «Использование» 2×2 grid «Сессий» / «Минут» / «Ответов AI» / «Токенов»; panels «Экспорт данных» and «Удалить всё» | `GET /v1/me/data/export` |
| `account.cabinet.data.export-none` / `export-pending` / `export-ready` / `export-failed` | export → `null`; `{status:"pending"\|"running"}` (polls every 3 s); `{status:"ready", download_url}`; `{status:"failed"}` | «Запросить архив» / «Готовим архив…» / extra «Скачать архив» + «Ссылка действует 24 часа…» / red «Не удалось собрать архив. Попробуйте позже.» | `DataExportJob` (`/root/whisperer/frontend/src/features/account/api.ts:15-22`) |
| `account.cabinet.data.export-requested` | click «Запросить архив» | toast «Собираем архив. Пришлём ссылку на почту, когда будет готов.» | `POST /v1/me/data/export` |
| `account.cabinet.data.purge-confirm` / `purge-done` / `purge-failed` | «Удалить всё» → confirm modal; then toast «Все данные удалены.» or «Не удалось удалить данные.» | | `POST /v1/me/data/purge {confirm_email}` → `{files_removed}` |
| `account.cabinet.data.toggle-error` | PATCH fails | «Не удалось сохранить режим no-logs» / «Не удалось сохранить настройку» | `PATCH /v1/me/profile` |

Hazards: the timezone row shows the current time (CabinetSettings.tsx:608-618); the timezone list comes from `Intl.supportedValuesOf`; `.pop` card animation; font tiles load all role CSS (`ensureAllRoles`); hover styles are written inline.

## Billing (inside the cabinet) and paywalls

UI: `/root/whisperer/frontend/src/features/billing/ui/*`. API: `/root/whisperer/frontend/src/features/billing/api/billing.ts`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `billing.subscription.loading` | `/v1/me` delayed | `svg.spin` under «Тариф» | `GET /v1/me` |
| `billing.subscription.free` | `subscription.tariff.code="free"` | Big tariff name, Tag with the **raw status** (`active`), facts «Осталось дней» (or «бессрочно»), «Лимит минут» (or «безлимит»), «Кредиты» «0 ₽»; minutes meter «Минуты 12 / 60» + «Осталось 48 мин» | `/v1/me`, `GET /v1/tariffs`, `GET /v1/me/billing/auto-renew`, `GET /v1/me/billing/credits/options` |
| `billing.subscription.exhausted` | `quota.exhausted:true` (or ≥ 90 % used) | Red meter + «Лимит исчерпан — обновите тариф, чтобы продолжить.» | |
| `billing.subscription.none` | `subscription:null` | «Подписка не найдена.» | |
| `billing.subscription.grace` | auto-renew `issue.in_grace:true` with `access_until` | Fact «Доступ до {date}» | |
| `billing.issue.declined` / `processing` / `awaiting` / `exhausted` | auto-renew `issue.kind` | Banner `[role=status]`. Texts: «Не удалось оплатить продление. Доступ сохранится до {d}, следующая попытка — {d}.» / «Банк ещё обрабатывает оплату продления…» / «Ждём продление от платёжной системы…» / «Оплатить продление не удалось, автопродление отключено…». `declined` and `exhausted` have a red border + «Сменить карту». Shown in both tabs. | auto-renew |
| `billing.premium-limits` | `user.features.premium_weekly_remaining_pct` not null (Max) | «Premium-модели · недельный лимит», «Premium-модели NN%», «Кредиты: {amount}»; if `options.available`: suggested amounts + input + «Пополнить» | `POST /v1/me/billing/credits/checkout` |
| `billing.tariffs.grid` | `/v1/tariffs` → `TariffOut[]` (codes `free`, `start`, `pro_1m/6m/1y`, `max_1m/6m/1y`) | «Тарифы»; Free + Start cards; duration selector «Месяц» / «Полгода» / «Год» (only if more than one is visible); Pro/Max cards; current card yellow with «ваш» + «Активная подписка»; Free card shows «Бесплатно по умолчанию»; savings tag «−NN%» + «≈ X/мес — выгоднее помесячной на NN%». Cheaper or shorter plans are hidden when a paid plan is active (TariffPlans.tsx:160-169). | |
| `billing.upgrade.methods` | `GET /v1/me/billing/methods` → more than one method | Buttons «МИР» / «МИР / Visa / MC» / «Visa / MC / Maestro» / «PayPal»; checkbox «Автоматически продлевать подписку» (if `supports_recurring`); «Списать бонусы (N ₽)» if the referral balance > 0; promo placeholder «Промокод (необязательно)»; «Перейти к оплате» | methods |
| `billing.upgrade.unavailable` | methods `[]` | «Оплата временно недоступна. Попробуйте позже.» | |
| `billing.promo.invalid` / `percent` / `days` / `affiliate` | type a promo and blur | «Промокод не найден или не действует» / «Скидка 10% (−99 ₽) будет применена» / «+7 дн подписки после оплаты» / «Affiliate-код принят — без скидки, поддерживает блогера» | `POST /v1/me/billing/promo-check` |
| `billing.checkout.preparing` / `error` / `already-done` | checkout pending; 500; detail `payment_already_completed` | «Готовим оплату…»; toast «Не удалось начать оплату. Попробуйте ещё раз.»; success toast «Предыдущая оплата уже прошла — всё зачислено…» | `POST /v1/me/billing/checkout` |
| `billing.checkout.redirect` | `CheckoutOut` without `widget` | `location.href = payment_url`. Dev stub: URL contains `/billing/checkout` → `POST /v1/me/billing/dev-confirm`, then `location.href="/cabinet?paid=1"` (**no `/app` prefix**, UpgradeButton.tsx:148-151) | |
| `billing.checkout.sheet` / `broken` / `settling` | `widget` present | Modal «Оплата» (blurred backdrop) with «Тариф Pro (30 дн.)» + amount; CloudPayments form; broken: «Форма оплаты не загрузилась…»; settling: «Подтверждаем оплату…» | script `widget.cloudpayments.ru/bundles/paymentblocks.js`; `GET /v1/me/billing/transactions/{id}` every 2 s for up to 40 s |
| `billing.pay-return.*` | `/app/cabinet?paid=1` or `?paid=0`; optional `sessionStorage["whisperer.pendingTx"]` | **Toasts show raw keys** «cab.paySuccess» / «cab.payFailed» / «cab.payProcessing». With a pending transaction: persistent info toast «Проверяем оплату…» first. See Findings. | transaction poll |
| `billing.billing.loading` | auto-renew delayed | Whole tab shows a spinner | |
| `billing.billing.no-card` | `method:null` | Card row placeholder «Карта не сохранена. Привяжите её, чтобы подписка продлевалась сама.» + «Привязать карту» (if eligible and no `renewal_provider`) | |
| `billing.billing.card` | `method:{mask:"4242",exp:"12/27",brand:"visa"}` | «•••• 4242», «Действует до 12/27», «Сменить карту», «Удалить карту» | `DELETE /v1/me/billing/payment-method` → toast «Карта удалена» / «Не удалось выполнить действие» |
| `billing.renewal.not-eligible` / `on` / `off` | `eligible:false`; `enabled:true` + `next_charge`; `enabled:false` | «Автопродление включается при оплате…» / Tag «Включено» + «Следующее списание 990 ₽ — {date}» + «Отключить автопродление» / Tag «Отключено» + «Доступ сохраняется до конца оплаченного периода.» + «Включить автопродление» | `POST …/auto-renew/disable` and `/enable` → toasts «Автопродление отключено» / «Автопродление включено»; enable 409 → «Сохранённой карты нет…» |
| `billing.history.empty` / `rows` | transactions `[]` / rows | «Платежей пока нет» / table «Дата», «Сумма», «Статус» with «Оплачен» / «Возврат», plus note «Фискальный чек присылает на вашу почту платёжная система.» | `GET /v1/me/billing/transactions` |
| `billing.card-sheet.tab` / `form` / `stuck` / `broken` | «Сменить карту» → binding with no widget / with widget / form after 25 s / script blocked | `dialog[aria-label="Карта для автопродления"]`: hold hint «Чтобы проверить карту, банк заморозит {amount}…» or «Банк проверит карту без списания денег.»; tab phase «Открыть форму банка» + «Ждём подтверждения банка…»; help «Форма пустая или не приходит код?» | `POST /v1/me/billing/payment-method/binding`; polls `GET …/binding/{id}` every 2 s |
| `billing.card-sheet.errors` | binding 429 `too_many_card_bindings` / `not_eligible` / other | «Слишком много попыток за сутки. Попробуйте завтра.» / «Автопродление включается при оплате…» / «Сменить карту сейчас нельзя. Попробуйте позже.» | |
| `paywall.premium-locked` | Free user on `/context`, `/knowledge-base`, `/storage`, `/settings/integrations`, or the calendar integrations tab | `PageHeader` + banner «Нужна подписка» / ««{раздел}» доступна только на платной подписке (Start, Pro или Max)…» / «Перейти к тарифам». Storage on Start: «Хранилище на Pro и Max». | — |

**Shapes** (`/root/whisperer/frontend/src/features/billing/contracts/types.ts`):
- `CabinetOut` 21-25; `PaymentMethods` 40-44; `CheckoutOut` 46-57; `CreditOptions` 62-73
- `AutoRenewStatus` 91-104; `PaymentIssue` 111-118; `CardBindingOut` 121-129; `CardBindingStatusOut` 133-137
- `TransactionRow` 141-151; `PromoCheckOut` 153-161; `TransactionStatus` 163-172
- `TariffOut` / `SubscriptionSummary` / `UsageSummary` / `QuotaSnapshot`: `/root/whisperer/frontend/src/shared/entitlements/types.ts:15-66`

**Paid gate:** `isPaidActive` requires status `active`, a tariff that is not `free`, and `expires_at` in the future (`/root/whisperer/frontend/src/shared/entitlements/subscription.ts:9-15`). This is clock-dependent.

Paywall code: `/root/whisperer/frontend/src/shared/entitlements/PremiumBanner.tsx:25-83`.

## `/referral` (access `auth`, inside the shell; user, also reachable by admin)

Page: `/root/whisperer/frontend/src/features/referral/pages/ReferralPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `referral.loading` | delay `GET /v1/me/referral` | Header «№13» «Рост» «Реферальная программа» + spinner | `GET /v1/me/referral` → `ReferralOut` (`/root/whisperer/frontend/src/features/referral/contracts/types.ts:2-16`; `api/referral.ts:12`) |
| `referral.populated` | data returned | «Ваша реферальная ссылка» with `<code>` showing `{origin}{link}`, «Копировать», «Код: ABC», reward line «… за каждого приглашённого…», stats «Приглашено», «Оплатили», «Бонусы на подписку» | same |
| `referral.copied` | grant clipboard permission, click «Копировать» | «Скопировано» for 1.5 s | — |
| `referral.error` | GET → 500 | **Spinner forever** (no error UI) | same |
| `referral.mobile` | ≤ 860 px | single column | — |

Hazard: the link includes `window.location.origin`, so the host and port appear in the screenshot.

## `/download` (access `auth`, inside the shell)

Page: `/root/whisperer/frontend/src/features/downloads/pages/DownloadPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `downloads.loading` | builds delayed | «№14» «Приложение» «Скачать приложение» + spinner | `GET /v1/app/builds` (`AppBuild[]`) |
| `downloads.empty` | `[]` **or an error** | «Сборки пока не опубликованы» / «Загляните позже — мы готовим релиз.» | same |
| `downloads.populated` | builds for `macos` / `windows` | `[data-onboarding="download-builds"]` cards headed by `platform_label`, dark buttons with version tag + size (e.g. «85,3 МБ») | same |
| `downloads.linux-limitations` | a build with `platform:"linux"` | Note «Недоступно на Linux» + 3 items (`/root/whisperer/frontend/src/features/downloads/contracts/limitations.ts:18-20`) | same |
| `downloads.click` | click a build link | Navigates to `download_url` | `POST /v1/me/onboarding/progress {done_action:"desktop_downloaded"}` |

The layout does not depend on platform; `desktopPlatform()` is used only for analytics (:27-33).

## `/hotkeys` (access `auth`, inside the shell)

Page: `/root/whisperer/frontend/src/features/hotkeys/pages/HotkeysPage.tsx`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `hotkeys.loading` | GET delayed | «№12» «Десктоп» «Горячие клавиши» + spinner card | `GET /v1/me/hotkeys` → `{hotkeys: HotkeyMap}` (`/root/whisperer/frontend/src/features/hotkeys/api.ts:5`; `contracts/types.ts:3-8`) |
| `hotkeys.populated` | map **with all 22 actions** (`contracts/types.ts:17-39`) | 22 rows: labels «Открыть приложение», «Старт / пауза записи», …; binding text such as «⌥ ⌘ Z» | same |
| `hotkeys.recording` | click a binding button | Yellow «Нажмите клавиши…»; a capture-phase keydown listener is active | — |
| `hotkeys.saved` | **Unreachable with the draft API** (checked in step 3b of D2): the frontend sends all 22 actions, `HotkeysUpdate` accepts at most 16 (`/root/whisperer/backend/src/meetassist/api/me.py:158-160`), so every save ends in 422 and `hotkeys.error-save`. Not in the screenshot matrix. | New label; no "saved" text is rendered | `PUT /v1/me/hotkeys {hotkeys}` |
| `hotkeys.error-conflict` | **Unreachable with the draft API** for the same reason: the length check answers 422 with a list `detail` before any conflict check. Not in the screenshot matrix. | «Комбинации не должны повторяться» | same |
| `hotkeys.error-save` | PUT with no string detail, or network failure | «Не удалось сохранить» | same |
| `hotkeys.error-load` | GET → 500 | spinner forever | — |
| `hotkeys.crash` | a map missing any action | route error fallback | — |

Binding labels use Mac symbols ⌃⌥⇧⌘ on every OS (`/root/whisperer/frontend/src/features/hotkeys/model.ts:3-8,58-63`).

---

## Cross-cutting notes

### Minimum API responses every signed-in page needs

Storage seed:
```
localStorage["wh-auth"] = {"state":{"csrfToken":"x","user":<UserMe>},"version":0}
localStorage["wh.lang"] = "ru"
localStorage["wh.theme"] = "light"
```

Set `user.language:"ru"` (otherwise the profile language wins) and a non-null `user.timezone` (otherwise a PATCH is sent).

| request | response to return |
|---|---|
| `POST /v1/auth/refresh` | `{access_token:"<no-space token>", token_type:"Bearer", expires_in:900, csrf_token:"x"}`. Any string works; tokens that are not JWTs are treated as "not expiring". |
| `GET /v1/auth/me` | Full `UserMe`, identical to the persisted user to avoid flicker. Free: `subscription.tariff.code:"free"`. Paid: e.g. `pro_1m`, `status:"active"`, `expires_at` far in the future or null. `features.premium_weekly_remaining_pct:null` hides premium limits. `appearance:{font:"whisperer"}`. |
| `GET /v1/me` | `CabinetOut`. `quota.limit_minutes:null` drops the ticker's minutes item. |
| `GET /v1/ticker` | `{}` (only date, tip and build remain) |
| `GET /v1/app/builds` | `[]` (version falls back to «1.4.2») or fixed builds |
| `GET /v1/me/tickets/unread-count` | `{"count":0}` |
| `GET /v1/me/onboarding` | `{"status":"completed","audio_status":"declined","version":1,"current_step":null,"completed_steps":[],"done_actions":[],"started_at":null,"completed_at":null}` (no tour, no launcher) |
| `POST /v1/satisfaction/prompt` | `{"due":false,"survey_id":null,"next_due_at":null}` |
| `POST /v1/analytics/collect` | 204 |
| `GET /v1/health` | 200 |

Background extras to stub (failures are swallowed):
- `GET /v1/admin/prompts` (prefetch, also for users)
- `GET /v1/me/referral`
- `GET /v1/admin/context` (paid only)
- WebSocket `/v1/ws/user` (block it or accept it)
- `GET /v1/i18n/detect` (only without `wh.lang`)

Admin additionally needs `GET /v1/admin/tickets/unread-count` and `GET /v1/admin/costs/summary?group_by=provider`. The home route also needs the analytics endpoints listed above.

### Theme and locale switching

**Theme:**
- `wh.theme` is `light|dark|system`; the default is `light`, not system (`/root/whisperer/frontend/src/shared/stores/themeStore.ts:41-49`; index.html:64).
- `system` follows `prefers-color-scheme` live (:111-118).
- Applied as `html[data-theme]`. A switch adds `.theme-anim` for 400 ms (320 ms transitions) (:62-73; globals.css:418-422).
- Toggles: cabinet tiles, Ctrl/Cmd+Shift+L in the shell, palette «Переключить тему».
- Theme is not synced to the server. Font is: `user.appearance.font` → `html[data-font]` + `wh.appearance` (`/root/whisperer/frontend/src/shared/theme/apply.ts:36-75`). A server value is adopted unless a local edit happened within the last 5 s.
- The login poster is always dark.

**Locale:**
- Chain: `wh.lang` → browser → `/v1/i18n/detect` → `en`; then the profile language overrides (`/root/whisperer/frontend/src/shared/i18n/index.ts:51-130`).
- The switcher (`/root/whisperer/frontend/src/shared/ui/LanguageSwitcher.tsx`; compact code on login, endonym in the cabinet) calls `changeLanguage`: i18next, then `wh.lang`, then `PATCH /v1/me/profile {language}` when logged in (:133-151).
- `html[lang]` uses `zh-Hant` for `zh`. Font role CSS is `/fonts/roles-<lang>-<role>.css`.
- **Playwright's default `navigator.languages` is `en-US`.** Always seed `wh.lang`.

### RTL (ar)

- `applyDocumentLocale` sets `html[dir=rtl]` after i18n initialises (`/root/whisperer/frontend/src/shared/i18n/localeStore.ts:25-33`; `LOCALES` at `locales.ts:24`).
- The inline script sets only `lang`, so there is a brief LTR first frame.
- Layout uses logical utilities (`start/end`, `ps/pe`, `border-e`).
- Ticker uses the `ticker-rtl` keyframes (globals.css:522-538).
- Toast and retry bars use `rtl:origin-right`.
- Icons in `MIRRORED_IN_RTL` get `.rtl-mirror` (`/root/whisperer/frontend/src/shared/ui/Icon.tsx:214`; globals.css:898).
- Tour arrow keys flip (Coachmark.tsx:131-133).
- All in-scope catalogs exist in ar. There is no ar audio walk, so the welcome modal has no «Послушать Leo».
- To get ar: `wh.lang="ar"` **and** `user.language="ar"`.

### Mobile breakpoints

Mobile is ≤ 860 px, tablet 861–1024 px (`/root/whisperer/frontend/src/shared/hooks/useMediaQuery.ts:21-28`). Tailwind's `md` breakpoint is deliberately not used.

On mobile:
- No in-flow sidebar; an off-canvas drawer opens via the TopBar menu (AppShell.tsx:145-161).
- TopBar gets a 44 px second row with breadcrumbs and an avatar (TopBar.tsx:148-218).
- Main padding changes from 18/44 px to 14 px.
- **There is no bottom navigation.**
- The cabinet becomes full-screen with stacked tabs.
- The login poster is hidden.
- Referral and data panels become single-column; `PageHeader` stacks.

On tablet the sidebar defaults to the 66 px rail. The sidebar width is exported as `--app-content-left` (260 / 66 / 0) on `:root`.

### Non-determinism hazards and suggested pins

- **Clock and date:**
  - Ticker date; timezone current time.
  - `isPaidActive` vs `expires_at`.
  - `formatDay` and analytics calendar (browser tz).
  - Countdowns: verify resend 60 s, connection elapsed and countdown, toast bars.
  - Pin with `page.clock` and a fixed `timezoneId`.
- **`Math.random`:** ticker tip (seed `Math.random=()=>0` to get «Совет: режим System Design помогает на технических интервью»); Leo message ids.
- **Animations:** `.ticker` (60 s infinite, ignores reduced-motion), `.rise`, `.pop`, `.pulse-y`, `.spin`, `.cursor` blink, `theme-anim`, `conn-*`, toast bars, poster rAF, onboarding spotlight transition. Set `prefers-reduced-motion: reduce` **and** inject `*{animation:none!important;transition:none!important}`.
- **Autofocus and caret:** login email/name/code, reset password, palette input (focus after 10 ms), tour card focus, Turnstile.
- **External scripts and iframes:** Yandex Metrika (index.html, webvisor), GA4 gtag, Cloudflare Turnstile, Google GSI, Yandex suggest SDK, VK ID SDK iframes, CloudPayments widget, `whisperer://` navigation.
- **Polling and timers:**
  - `/v1/me` every 15 s; unread-count every 60 s.
  - Satisfaction POST at 25 s; analytics flush every 5 s.
  - WebSocket ping every 25 s with reconnect.
  - Export status every 3 s; transaction or binding polls every 2 s.
  - Captcha deadlines 6 / 9 / 18 / 45 s; card-sheet help after 25 s; route warm-up on idle callbacks.
- **`navigator`-dependent output:**
  - `isMac` → «⌘K» vs «Ctrl K» (`/root/whisperer/frontend/src/shared/lib/platform.ts:5-19`).
  - `desktopPlatform()` → welcome download label; headless Linux resolves to `linux` (:50-70). Pin the UA plus `navigator.platform` / `userAgentData`.
  - `navigator.languages`; `navigator.clipboard` (permission); Web Locks / BroadcastChannel.
  - Autoplay policy (audio walk).
  - `Notification.permission` / service worker (push).
- **Origin-dependent text:** the referral link.
- **Web fonts:** wait for `document.fonts.ready` after `/fonts/roles-*.css` loads.
- **Storage keys to reset:**
  - localStorage: `wh-auth`, `wh.theme`, `wh.lang`, `wh.appearance`, `wh.ft`, `wh.onb.audio`, `wh.push`, `whisperer-anonymous-id`, `whisperer-analytics-session:v1`, `agent-session-v1:<uid>`, the Leo chat store `…:<uid>`.
  - sessionStorage: `whisperer.pendingTx`, `vite-preload-reload-ts`.

### Findings / bugs worth recording as known states

1. **Payment-return toasts show raw keys.** v2 shows the translated texts (owner, 2026-10-01). `usePaymentReturn` translates `account:cab.paySuccess|payFailed|payProcessing` (`/root/whisperer/frontend/src/features/billing/hooks/usePaymentReturn.ts:17,53,62,83,85,87`), but those keys exist only in the billing catalogs (`/root/whisperer/frontend/src/features/billing/locales/ru.json:87-91`). The toasts read «cab.paySuccess» and so on. «Проверяем оплату…» is fine.
2. **The dev-stub payment redirect leaves the SPA base.** It goes to `/cabinet?paid=1` without `/app` (`/root/whisperer/frontend/src/features/billing/ui/UpgradeButton.tsx:150`).
3. **Hotkeys page crashes on an incomplete map.** `formatBinding(undefined)` throws when any of the 22 actions is missing. Also, any string `detail` is reported as «Комбинации не должны повторяться».
4. **Some load errors have no error UI.** `/referral` and `/hotkeys` spin forever; `/download` shows the empty state.
5. **Login and register errors are toast-only** (`state.error` is never rendered).
6. **The collapsed sidebar search tooltip hard-codes ⌘** in the ru string «Поиск (⌘K)» on every OS.
7. **`localeOf` falls back to `zh`** (`LOCALES[1]`) for unknown codes (`/root/whisperer/frontend/src/shared/i18n/locales.ts:49-51`).
8. **The `index.html` comment about SmartCaptcha is stale.**
9. **Hotkeys are never saved.** The page sends the whole map of 22 actions; the API allows 16 entries and answers 422. Every change ends in «Не удалось сохранить». Found while recording in step 3b of D2.
10. **⌘K while recording a hotkey also opens the command palette.** The page's capture-phase listener records the combination but does not stop the event, and the palette's own listener opens over the page. The harness records ⌥⌘J for this reason.

### Coverage in the screenshot matrix (step 3b of D2)

Every state of this document is either a state in the registry ([src/states/](../src/states/)) under its own id, captured inside another screenshot, or left out for a stated reason. Tour steps on routes of other groups (5–18) are captured with those groups, on their fixtures.

**Captured inside another state:**

| state | screenshot |
|---|---|
| `auth.login.poster`, `auth.login.mobile`, `auth.login.social-ru` | `auth.login.default` (desktop and mobile cells; the recording runs with `CF-IPCountry: RU`) |
| `auth.login.social-tip-open` | `auth.login.social-tip` |
| `auth.connect.anon` | `auth.connect.anonymous` |
| `auth.login.success`, `auth.login.redirect-authed`, `onboarding.welcome-later`, `onboarding.tour.later`, `onboarding.tour.skip` | `shell.user`: each ends on the signed-in home |
| `boot.refresh-dead`, `account.cabinet.profile.logout`, `account.cabinet.profile.delete-success` | `auth.login.default`: each ends on the sign-in page |
| `boot.refresh-network`, `shell.connection-probing`, `shell.connection-calm` | `shell.connection-lost` (probing, reduced motion) |
| `shell.desktop-full`, `shell.nav-active`, `shell.hub-beta`, `shell.ticker` | `shell.user` |
| `shell.theme-toggle`, `account.cabinet.general.theme-dark` | the dark cells of every full-scope state |
| `shell.palette.kb-loading` | `shell.palette.searching` (both texts show together) |
| `shell.toast.error`, `success`, `info` | the error states, `account.cabinet.data.purge-done`, `account.cabinet.data.export-requested` |
| `onboarding.tour.step-N.cta` | `onboarding.tour.step-3`, `onboarding.tour.step-21` |
| `onboarding.tour.step-N.paid-locked` | `onboarding.tour.step-23`, `onboarding.tour.step-24` |
| `onboarding.launcher-resume` | the tour steps (sidebar «Продолжить обучение») |
| `onboarding.restart` | `onboarding.tour.step-1` |
| `account.cabinet.subscription`, `billing.tariffs.grid`, `billing.upgrade.methods` | `billing.subscription.*` |
| `account.cabinet.data.export-none` | `account.cabinet.data` |
| `account.cabinet.general.marketing-off` | `account.cabinet.general`: the seeded users have not agreed to mailings |
| `account.cabinet.billing` | `billing.payments.*` (the «Оплата» tab) |
| `billing.premium-limits` | `billing.subscription.max` |
| `billing.billing.card`, `billing.renewal.not-eligible`, `.on`, `billing.history.empty`, `.rows` | `billing.payments.card`, `billing.payments.empty` |
| `billing.card-sheet.errors` | `billing.card-sheet.too-many`, `not-eligible`, `unavailable` |
| `referral.mobile` | the mobile cells of `referral.populated` |
| `hotkeys.crash` | `route.error-fallback` (the same trigger) |

**Not screenshotted:**

| state | reason |
|---|---|
| `auth.login.error-too-many`, `hotkeys.saved`, `hotkeys.error-conflict` | unreachable with the draft API (see the rows above) |
| `billing.pay-return.*` | the toasts show raw translation keys (finding 1). **Decided by the owner on 2026-10-01: v2 shows the translated texts** («Оплата прошла…» and the rest of `billing:cab.paySuccess`, `payFailed`, `payProcessing`), so the draft's screen is not a baseline. The billing slice checks these toasts with its own tests |
| `referral.error`, `hotkeys.error-load` | render exactly as `referral.loading` and `hotkeys.loading` (finding 4) |
| `auth.login.social-return-busy` | no visible change: the submit button is disabled, as on an empty form |
| `auth.captcha.loading`, `ready`, `solved`, `dead`, `stalled` | the Turnstile widget is a third-party script; the harness stubs it with a fixed 300 × 65 frame |
| `auth.verify.resend-ready`, `auth.verify.resent`, `auth.verify.resend-failed` | the resend button unlocks after 60 s on a real timer |
| `auth.reset.done` | lives 1.8 s on a real timer, then navigates to `/login`, which is screenshotted |
| `referral.copied` | lives 1.5 s on a real timer and needs clipboard permission |
| `boot.i18n-pending` | an empty `#root` for the moment before React mounts |
| `route.loading`, `account.cabinet.loading` | a lazy chunk loading; the harness serves chunks from disk at once and overrides only `/v1` |
| `shell.connection-retry-n` with N > 1, `shell.connection-rebooting`, `shell.connection-easter-egg` | timers on the real clock (backoff, 900 ms reboot) |
| `shell.toast.warning` | no flow of this group raises a warning toast |
| `shell.tablet` | the tablet layout is not in the matrix (plan §2) |
| `onboarding.audio.*` | subtitles follow the playback time of an mp3 |
| `billing.checkout.sheet`, `.broken`, `.settling`, `billing.card-sheet.form`, `.stuck`, `.broken` | the CloudPayments widget is a third-party script and iframe; the harness stubs third-party scripts |
| `billing.checkout.redirect`, `downloads.click` | navigate away from the app |
| `account.cabinet.leo`, `account.cabinet.mcp` | belong to the Leo and MCP features (step 5) |
| `paywall.premium-locked` | renders on routes of other groups; captured with them |
