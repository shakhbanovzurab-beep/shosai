> Draft commit `589917e847f7d7213b3af5a3959bcc88c7500fe7`, read on 2026-10-01. File paths and line numbers refer to `/root/whisperer/frontend` at that commit.

# UI state inventory: rooms, streams, storage, tracker

All paths below are relative to `/root/whisperer/frontend/src/`. Every SPA URL is served under `/app/` (`vite.config.ts:103`), so `/rooms/abc` is really `/app/rooms/abc`. Line numbers come from the source files. Where I computed them from concatenated output they may be off by about 1.

**Access model** (`app/router/guards.tsx`, `app/router/buildRoutes.tsx`):
- `public` and `auth` routes go through `AccessGate` without a check. Inside-shell routes are protected by the shell's `RequireAuth`: with no `accessToken` and no persisted `user` it sends you to `/login`.
- `admin` uses `RequireAdmin`: a non-admin user is sent to `/analytics`.
- Each route has its own `ErrorBoundary` and `Suspense`. Lazy screens wait for the chunk and the i18n namespace (`shared/lazyScreen.ts`).
- Auth is persisted in `localStorage["wh-auth"]` as `{csrfToken, user}` (`shared/auth/authStore.ts:27-28`). The access token lives only in memory. A 401 on the shared `api` client triggers `POST /v1/auth/refresh`; if that also fails, the session is cleared (`shared/api/client.ts:262-276`).

**Paid check:** `isPaidActive(user)` (`shared/entitlements/subscription.ts:9-15`) requires `subscription.status === "active"`, `tariff.code !== "free"`, and `expires_at` later than `Date.now()`.

---

## /rooms/:id (RoomPage: host entry)
- Access `public`, outside the shell (`features/rooms/feature.ts:41`). The page has its own sign-in gate (`pages/RoomPage.tsx:34,61-69`): "signed in" means `accessToken || user`.
- The token request needs an account. Rooms are free on any tariff (comment at :36).
- Host-only extras inside the room:
  - **Recording**: needs `GET /v1/me/storage/stats` with `limit_bytes > 0`, i.e. Pro/Max (`hooks/useRecording.ts:77-85`).
  - **AI assistant**: needs `JoinInfo.ai_assistant === true` (the server sets this when the host is on Start/Pro/Max) and no E2EE (`model/identity.ts:346`).
  - **Subtitles**: gated by the server. A non-paid host gets a `subscription` failure message.
- Example URL: `/app/rooms/7f3c…` (E2EE: `/app/rooms/7f3c…#key=<base64url>`).

### Before media: entry and pre-join states

| state id | how to reach (URL + data + interaction) | marker | endpoints |
|---|---|---|---|
| `rooms.host.signin-required` | No `user` in `wh-auth` and no token. No request is made. | h1 "Нужен вход" + button "Войти в Whisperer" (navigates to `/login`). Body text starts "Эта ссылка ведёт в комнату её владельца…". Eyebrow "Студия". | none (`RoomPage.tsx:61-69`) |
| `rooms.host.loading` | Signed in; `POST /v1/me/rooms/{id}/token` still pending. | Full-screen `div.fixed.inset-0` with only `svg.spin`. No h1, no `.vroom`. | token + info (below) |
| `rooms.host.finished` | Token POST returns 409 `{detail:"room_closed"}` or 404 `{detail:"room_finished"}` (`api/rooms.ts:64-74`). | h1 "Встреча завершена", text "Встреча завершена. Ссылка-приглашение больше не действует.", button "К календарю". | token |
| `rooms.host.error` | Token POST returns any other error (500, 403, network). Detail `registration_required` or `admission_denied` also lands here. | h1 "Не удалось войти" (card has `border-destructive`), text "Не удалось войти в комнату", no button. | token |
| `rooms.host.signin-required` (after 401) | Token POST 401 → refresh 401 → `clearSession()`. `signedIn` becomes false. | Same as the first row. | token, `POST /v1/auth/refresh` |
| `rooms.prejoin.permission-pending` | Token succeeds. `navigator.mediaDevices.getUserMedia({audio,video})` has not settled (`hooks/useMediaDevices.ts:36`). | h1 "Присоединиться к встрече", black `video[aria-label="Камера"]` box, toggles "Микрофон вкл" / "Камера вкл". No combobox selects, no red text. | none |
| `rooms.prejoin.granted` | getUserMedia resolves (Playwright `--use-fake-device-for-media-stream` + granted permissions). | Two Radix `role=combobox` selects labelled "Камера" and "Микрофон" (`ui/PreJoin.tsx:137-140`). Live mirrored preview. | none |
| `rooms.prejoin.denied` | getUserMedia rejects (permission denied, no devices, or insecure context). Both toggles switch off (`useMediaDevices.ts:48`). | Red box "Нет доступа к камере/микрофону. Проверьте разрешения браузера — войти можно и без них." + placeholder "Камера выключена" + danger buttons "Микрофон выкл" / "Камера выкл". | none |
| `rooms.prejoin.cam-off` | From granted, click "Камера вкл". | Button text "Камера выкл" (danger) + `videoOff` icon with "Камера выключена". | none |
| `rooms.prejoin.mobile` | Viewport ≤860px (`useIsMobile`). | Toggle labels are just "Микрофон" / "Камера" (`PreJoin.tsx:119-131`). | none |

Interaction to leave pre-join: click the dark button "Присоединиться к встрече" (it has the same text as the h1, so target `button` by role+name). This stops the preview tracks and mounts `VideoRoom`.

### In the room (VideoRoom, shared by host and guest; `ui/VideoRoom.tsx`)

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `rooms.room.connecting` | After Join, before `room.connect()` resolves (`hooks/useLiveKitRoom.ts:103`). The LiveKit WebSocket can be held pending. | `.vroom` root; stage `.vroom-stage-scroll` shows only a spinner. Desktop: HUD pill `.vroom-hud` with a spinner and no text. Dock `.vroom-dock` is fully rendered. Mobile: no status chip at all. | LiveKit WS |
| `rooms.room.connect-error` | LiveKit WS fails or is refused (`useLiveKitRoom.ts:131`). | Desktop HUD text "Не удалось подключиться" (red). Mobile `.vroom-chip` with the same text. The stage spinner stays forever. | LiveKit WS + `GET …/rtc/v1/validate` |
| `rooms.room.connected.grid` | Real or emulated SFU. Default layout is "grid". | `.vroom-tile` elements. HUD "N · Участники · 00:07" with `span[role=timer][aria-label="Продолжительность встречи"]`. | SFU |
| `rooms.room.connected.e2ee` | `JoinInfo.e2ee=true` and `#key=` in the URL. | HUD "Подключено (шифрование)" with a shield icon. No record button, no AI item. | SFU, E2EE worker |
| `rooms.room.layout.gallery` / `.focus` | Desktop: click `button[aria-label="Галерея"]` or `"Фокус"` (`aria-pressed`). Mobile: chip `.vroom-chip-btn` with aria-label naming the target layout ("Фокус" / "Сетка"). | Focus: large tile plus a 120px strip. Pressed segment has `aria-pressed="true"`. | none |
| `rooms.room.tile.no-video` | A participant with no camera. | Yellow initials circle inside `.vroom-tile`; `micOff` icon in `.vroom-name`. | none |
| `rooms.room.chat.empty` | Click dock `button[aria-label="Чат"]` (desktop). On mobile it is in the "Ещё" menu. Works even while connecting or in error. | `.vroom-panel` header "Чат" + "Сообщений пока нет" (`ui/ChatPanel.tsx:54`). | none (data channel only) |
| `rooms.room.chat.populated` | Needs data-channel messages `{type:"chat"}`. Your own messages appear only when `room` exists. | Message rows with a left border; own rows use `border-primary`. | SFU |
| `rooms.room.chat.unread-badge` | Remote chat message arrives while the panel is closed. | `.vroom-badge` on the "Чат" button ("9+" above 9). | SFU |
| `rooms.room.reactions-picker` | Click `button[aria-label="Реакции"]`. | `.vroom-pop` with 6 buttons `aria-label="Реакции: 👍"` etc. (`ui/ReactionsOverlay.tsx:59-75`). | none |
| `rooms.room.reaction-floating` | Pick an emoji. Your own reaction shows locally only if `room` is non-null. | Absolutely positioned emoji in an `aria-hidden` overlay (animated). | SFU publishData |
| `rooms.room.more-menu` | Click `button[aria-label="Ещё"]`. | Context-menu `div.pop.fixed` (portal on body) with items "Доска", "Переводчик", and "AI-ассистент" if available. On mobile it also has "Демонстрация экрана", "Добавить участников", "Чат", "Реакции", and "Запись" if available (`ui/RoomControlBar.tsx:241-294`). | none |
| `rooms.room.device-menu` | Right-click or hold ≥450ms on the mic/cam button. Needs more than 1 device after connect (`useRoomDevices`). | Context menu listing device labels; the active one has a check icon. Mic/cam buttons show `.vroom-more-dot`. | none |
| `rooms.room.invite-modal` | Click `button[aria-label="Добавить участников"]`. Host: only when `GET /v1/me/rooms/{id}` succeeded. Guest: always. | `dialog[aria-label="Добавить участников"]` with readonly input, button "Скопировать ссылку", "Поделиться" if `navigator.share` exists, and hint "Отправьте ссылку — по ней присоединятся к встрече.". | none |
| `rooms.room.invite-modal.copied` | Click "Скопировать ссылку" (needs clipboard permission). | Button text "Скопировано" for 1.8s. | none |
| `rooms.room.translator.off` | "Ещё" → "Переводчик". | Panel header "Переводчик"; row "Субтитры с переводом" with button "Выключено"; selects "Собеседники говорят на" / "Показывать мне на"; swap button `aria-label="Поменять языки местами"`. Default languages are equal, so the hint "Языки совпадают — переводить нечего. Выберите разные, чтобы увидеть перевод." shows. | none |
| `rooms.room.translator.lang-differ` | Change one of the selects. | Hint "Речь собеседников распознаётся на первом языке…". | none |
| `rooms.room.translator.on-idle` | Click "Выключено", which becomes "Включено". With no room, no WS is opened. | Section "Что происходит" with "Слушаю. Скажите что-нибудь — фраза появится здесь." The "Отображение" segmented control is enabled. | WS `/v1/subtitles/stream` (only if connected) |
| `rooms.room.translator.listening` / `.ready` | Subtitles WS sends `subtitle.delta`. | "Распознаю…" with `.pulse-y` dot / "Реплик: N". | WS |
| `rooms.room.translator.failure-<code>` | WS `{"type":"error","code":X}`, WS error/close, or 4xx/5xx on `/v1/subtitles/translate`. | Red box. Texts: subscription "Субтитры доступны на платном тарифе"; quota "Кончились минуты перевода…"; premium "Исчерпан общий premium-лимит тарифа Max…"; e2ee "Во встрече со сквозным шифрованием субтитры недоступны"; denied "Нет доступа к субтитрам"; unavailable "Видеоинфраструктура недоступна"; recognition "Не удалось распознать фразу"; offline "Нет связи". | WS, translate |
| `rooms.room.translator.notepad` | Enabled + click segment "Блокнот". | "Пока тихо" when there are no lines. | none |
| `rooms.room.subtitles-overlay` | Translator enabled, view "Субтитры", board closed, lines exist. | `div[aria-live=polite][aria-label="Переводчик"]` with dark pills "Speaker: text". | WS |
| `rooms.room.ai.*` | "Ещё" → "AI-ассистент". Needs `JoinInfo.ai_assistant=true` and no E2EE. Opens even without an SFU. | Header "AI-ассистент". Chromium: toggle "Транскрипция идёт", or "Микрофон выключен — транскрипция на паузе" if the mic was off at pre-join, or "Транскрипция на паузе" after clicking. Firefox/WebKit: "Живой транскрипт доступен в Chrome/Edge…". Empty: "Начните говорить — транскрипт появится здесь". Footer "Сохранить в «Встречи»" is disabled with 0 lines. | see below |
| `rooms.room.ai.thinking` / `.answer` / `.error` | Type into `input[aria-label="Спросить о встрече"]` and press Enter (POST is plain HTTP, replayable). | "Думаю…" with spinner → answer box + model name → or red error: "AI-ассистент доступен на тарифах Start, Pro и Max." / "Слишком много вопросов подряд — подождите минуту." / "Не удалось получить ответ. Попробуйте ещё раз." | `POST /v1/meeting-ai/ask` |
| `rooms.room.ai.saved` / `.save-error` | Needs transcript lines, then click save. | Link "Открыть в «Встречах»" (href `/meetings/{id}`, no `/app` prefix) / "Не удалось сохранить". | `POST /v1/me/sessions/from-transcript` |
| `rooms.room.record.idle` / `.busy` / `.active` / `.stopping` | Host only, not E2EE, stats `limit_bytes>0`. Desktop: dock button `.vroom-rec`. Mobile: "Ещё" menu item. | aria-label "Запись" (red dot) → spinner while pending → "Стоп" (`data-recording="true"`, pulse animation, `data-tone="danger"`) → "Останавливаем…". | start/stop/recordings |
| `rooms.room.record.error-toast` | Start or stop POST fails. | Toast `role=alert` "Ошибка записи". | |
| `rooms.room.board.*` | Needs **connected** (stage shows the board only when `status==="connected"`, `VideoRoom.tsx:136-142`). "Ещё" → "Доска". | `.vboard` with bar "Доска". Lazy chunk loading: spinner. Chunk failure: "Доска не загрузилась. Проверьте связь и откройте её снова.". Save state `.vboard-state`: "Сохраняю…" / "Сохранено" / "Не сохранено" / "Доска слишком большая" / "Без сохранения" (when `storable:false`). | whiteboard API |
| `rooms.room.board.formula` | Board → `button[aria-label="Формула"]`. | `.vboard-panel` "Формула"; "Здесь появится предпросмотр"; errors "Формула не разобрана — проверьте синтаксис" / "Формула слишком длинная"; when editing, title "Правка формулы" + "Заменить". | MathJax (local) |
| `rooms.room.board.export-menu` | Board → `button[aria-label="Скачать"]`. | Menu "Картинка PNG" / "Вектор SVG" / "Файл доски JSON". | none |
| `rooms.room.board-saved-toast` | After recording stop, with a non-empty board. | Toast "Доска сохранена в файлы". | scene GET + storage upload |

**Leaving:** host leave runs `window.close()` then navigates to `/calendar`. Guest leave goes back to PreJoin.

**Endpoints**
- `POST /v1/me/rooms/{id}/token` body `{}` → `JoinInfo` (`features/rooms/contracts/types.ts:1`). Errors are mapped in `api/rooms.ts:64-74` (`JoinFailure`, `types.ts:77`).
- `GET /v1/me/rooms/{id}` → `RoomInfo` (`types.ts:52`). Best-effort: on failure there is no invite button and the board title falls back to "Доска".
- **LiveKit (`livekit-client` 2.20)**: WebSocket `{JoinInfo.url}/rtc/v1?access_token=<JoinInfo.token>&…` (v0 fallback `/rtc`). On failure it does an HTTP GET `{http-url}/rtc/v1/validate`. Timeouts: websocket 15s, peer connection 15s. Then WebRTC ICE/DTLS. A region-settings fetch happens only for LiveKit Cloud hosts. If the connection fails, the page shows the spinner plus the "Не удалось подключиться" HUD; there is no retry.
- Data channel: chat/reaction (no topic), `transcript`, topic `subs`, whiteboard topics.
- Host only: `GET /v1/me/storage/stats` → `StorageStats` (`features/storage/contracts/types.ts:31`), `retry:false`. A 403 hides the record button.
  - `GET /v1/me/rooms/{roomId}/recordings` → `Recording[]` (`types.ts:38`). Polled every 5s while any item has `status==="recording"` (`useRecording.ts:14,30`).
  - `POST …/recording/start` → `Recording`.
  - `POST …/recording/stop` → `{stopped, recording}`.
- **Subtitles**: WebSocket `ws(s)://{host}/v1/subtitles/stream` with subprotocols `["whisperer-room-pass", <room token>]` (`api/subtitlesStream.ts:60`). The client sends `{"type":"hello","target_lang"}`. The server sends `ready`, `subtitle.delta{slot,text}`, `subtitle.end`, `error{code}`. Binary PCM frames go up.
  - `POST /v1/subtitles/translate` (Bearer room token) → `TranslatedPhrase` (`types.ts:122`). Errors are mapped in `api/subtitles.ts:32-43`.
- **AI**: `POST /v1/meeting-ai/ask` (Bearer room token) → `MeetingAnswer` (`features/meetings/api/meetingAi.ts`, `{answer, model}`). `POST /v1/me/sessions/from-transcript` → `{session_id}` (`api/rooms.ts:46`).
- **Whiteboard**: `GET /v1/whiteboard/scene` → `SceneState` (`types.ts:79`). `PUT /v1/whiteboard/scene` → `SceneSaved` (`types.ts:90`), autosaved after 2.5s idle, by the "primary" participant only. 409/413/401/403 are classified in `api/whiteboard.ts:56-79`. Load failure shows "Не сохранено" but the board still opens. Fonts load from `/app/wb/`.
- **After recording stop**: `GET /v1/whiteboard/scene` + `POST /v1/me/storage/upload` (multipart) → `StorageItem`.

**Hazards**
- `MeetingDuration` ticks every second from `Date.now()` (`ui/MeetingDuration.tsx:45`).
- Reactions use `Math.random()` for horizontal position and a 3.8s Web Animations API animation.
- `.pulse-y` animation; `.vroom-rec` pulse.
- Camera `<video>` elements: pre-join preview and tile `track.attach()`.
- Web Speech API auto-starts when AI is enabled (Chrome sends audio to Google).
- AudioContext + ScriptProcessor capture for subtitles.
- Whiteboard publishes a `canvas.captureStream` track at 10fps while recording; Excalidraw canvas, cursors, `PEER_COLORS`.
- Recordings poll every 5s.
- E2EE `new Worker(new URL("livekit-client/e2ee-worker"))` may fail and silently degrade to a normal room.
- Chat auto-scrolls with `scrollIntoView`.
- The ContextMenu closes on scroll/resize.

---

## /rooms/join/:invite (GuestJoinPage)
- Access `public`, outside the shell (`feature.ts:40`). Anonymous users are allowed.
- The invite link shown in the room is `${origin}/meet/${invite}${hash}`; `/meet/…` is a backend route, not the SPA.
- Example: `/app/rooms/join/AbCdEf123`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `rooms.guest.prejoin` (+ permission-pending / granted / denied / cam-off / mobile, same as host) | Open the URL. No request until Join. | Same PreJoin plus `input[aria-label="Ваше имя"]` (placeholder "Ваше имя"). | none |
| `rooms.guest.joining` | Click "Присоединиться к встрече"; POST pending. | Join button has `loading` (spinner inside the button). | join |
| `rooms.guest.unavailable` | POST join returns any non-finished error (404/500/network). | Red text under the form "Не удалось войти в комнату" (`PreJoin.tsx:153`). | join |
| `rooms.guest.finished` | POST join returns `{detail:"room_finished"\|"room_closed"}`. | MeetingNotice h1 "Встреча завершена" + "Встреча завершена. Ссылка-приглашение больше не действует." with **no** button. | join |
| `rooms.guest.registration` / `.denied` | Detail `registration_required` / `admission_denied`. | **No distinct UI.** PreJoin re-renders with no message (only `finished`/`unavailable` are rendered). | join |
| `rooms.guest.waiting` | Response `{status:"waiting", knock_token}`. | **No distinct UI.** Opts are set but info stays null, so PreJoin shows again with the preview stopped. `pollKnock` (`GET /v1/rooms/knock/{t}`) is never called. The waiting-room locale strings are unused. | join |
| `rooms.guest.redirect-stream` | Response `{status:"stream", watch_url}`. | Full navigation `window.location.replace(watch_url)`, i.e. to `/live/:token`. | join |
| in-room states | Response `{status:"joined", …JoinInfo}` (or no `status` field). | Same as the in-room table above. No record button (`roomId` undefined, so the stats call is skipped). Invite is always available. | as above |

**Endpoints**
- `POST /v1/rooms/join/{invite}` body `{name}` → `JoinPayload` (`api/rooms.ts:13`), converted to `JoinResult` (`types.ts:31`). The `api` client attaches a Bearer token if signed in.
- In-room traffic is the same as for the host, minus stats and recordings.

**Hazards:** same as the host page; the name input is not auto-focused.

---

## /admin/livekit (LivekitPage)
- Access `admin`, inside the shell (`feature.ts:42`).
- Admin role required. A non-admin is redirected to `/analytics`; an anonymous visitor to `/login`.
- All copy is hard-coded Russian.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `livekit.loading` | Health pending. | Header "Видео-инфраструктура" (eyebrow "LiveKit") + centered spinner. | health |
| `livekit.health.ok` | Health `{status:"ok", checked_at}` + stats. | Tag "SFU в норме", "проверено в HH:MM:SS", metrics "Комнат", "Участников", "Публикуют", "Подписок", "Записей идёт", "Нагрузка узла". Sections "Активные комнаты", "Записи", "Журнал вмешательств". | health, stats, egress, audit |
| `livekit.health.load-warn` | `stats.load_pct >= 75`. | "Нагрузка узла" value styled `text-destructive`. | stats |
| `livekit.health.down` | `{status:"down", detail:"not_configured"}`. | Tag "SFU недоступен", red card, "Видео-комнаты неактивны. SFU не сконфигурирован (нет ключей LIVEKIT_*) — функция дормантна." No sections. | health |
| `livekit.health.recording-off` | `recording_available:false`. | Tag "запись выключена". | health |
| `livekit.health.request-failed` | Health GET errors. | Misleading: Tag "SFU в норме" with no metrics and no sections (`health` undefined means "not down"). | health |
| `livekit.rooms.loading` | Stats pending. | Spinner inside "Активные комнаты". | stats |
| `livekit.rooms.empty` | `stats.rooms=[]`. | "Активных комнат нет." | stats |
| `livekit.rooms.populated` | Rooms present. | Table with headers "Комната / Владелец / Участники / Идёт / Состояние". Tags "запись", "E2EE", "закрыта в БД", "сирота" (domain null). Buttons "Завершить". | stats |
| `livekit.room.expanded.*` | Click `button[aria-label="Участники комнаты {title}"]` (`aria-expanded`). | Loading spinner / "Не удалось получить участников комнаты." / "В комнате никого нет." / participants table with tags "бот записи", "зритель стрима", "только смотрит", track tags "камера · выкл", buttons "Отключить". | room detail |
| `livekit.room.close-confirm` | Click "Завершить". | Popover `dialog[aria-label="Завершить комнату"]` with "Все участники будут отключены немедленно… Действие попадёт в журнал." and buttons "Отмена" / "Завершить". | close |
| `livekit.participant.kick-confirm` | Click `aria-label="Отключить {name}"`. | `dialog[aria-label="Отключить участника"]`. | remove |
| `livekit.egress.unavailable` | `{available:false}`. | "Запись выключена: не заданы ключи S3-хранилища. Это дормантный режим, а не сбой." | egress |
| `livekit.egress.empty` / `.active` / `.stuck` | `active:[]` / items / `stuck:[…]`. | "Активных записей нет." / status tags "идёт", "запускается"… + "Остановить" / red card "Зависшие записи" with "висит N мин". | egress |
| `livekit.egress.stop-confirm` | Click `aria-label="Остановить запись комнаты {room}"`. | `dialog[aria-label="Остановить запись"]`. | stop |
| `livekit.audit.empty` / `.populated` | `[]` / entries. | "Админы ещё не вмешивались в чужие звонки — журнал пуст." / rows with "завершил комнату", Tag "не удалось". | audit |

**Endpoints** (types in `features/rooms/api/admin.ts`)
- `GET /v1/admin/livekit/health` → `LkHealth` (:122). Refetched every 10s.
- `GET /v1/admin/livekit/stats` → `LkStats` (:35). Every 10s, only when health is ok.
- `GET /v1/admin/livekit/rooms/{name}` → `LkRoomDetail` (:96). Every 10s while expanded.
- `GET /v1/admin/livekit/egress` → `LkEgressOverview` (:104). Every 15s. On error the section renders nothing.
- `GET /v1/admin/livekit/audit?limit=30` → `LkAuditEntry[]` (:110).
- `POST /v1/admin/livekit/rooms/{name}/close`
- `POST /v1/admin/livekit/rooms/{name}/participants/{identity}/remove`
- `POST /v1/admin/livekit/egress/{id}/stop?lk_room=`

**Hazards**
- Polling every 10s and 15s.
- Relative times use `Date.now()` (`liveFor`, `joinedAgo`, `since`).
- Dates: `toLocaleTimeString("ru-RU")` and `toLocaleString("ru-RU")`, so timezone-dependent.
- `.rise` entry animation on cards.

---

## /live/:token (WatchPage: public stream viewer)
- Access `public`, outside the shell (`features/streams/feature.ts:42`). Anonymous users are allowed.
- Signed-in users skip the name prompt (`readName()` returns `""`). Guests remember their name in `localStorage["wh.stream.name"]`; a pending knock is kept in `sessionStorage["wh.stream.knock.<token>"]` (`hooks/useStreamEntry.ts:27,75`).
- Example: `/app/live/s_9Xk2…`.
- No camera or mic is requested from viewers. The LiveKit join uses `{micOn:false, camOn:false}`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `streams.watch.loading` | Join POST pending (name known). | Full-screen `svg.spin` only (`WatchPage.tsx:90-95`). | join |
| `streams.watch.name-required` | Anonymous, no `wh.stream.name`, no knock. The page fetches the card. | Card eyebrow "Трансляция", title = `card.title`, status strip "Как вас зовут?" / "Имя увидят ведущий и зал в чате…", Input label "Имя" placeholder "Например, Анна" (**autoFocus**), button "Смотреть эфир" (disabled while empty). Before the card arrives the strip shows without a title. | card |
| `streams.watch.broken` | Join fails and card GET fails, or card GET fails while asking for a name. | Strip (error tone) "Ссылка не работает" + "Проверьте адрес или попросите новую ссылку у организатора." No card. | join, card |
| `streams.watch.stuck-spinner` | Join fails but card GET succeeds (e.g. 403 registered-only). | **Infinite spinner** (`card` set, `entry` null, `outcome` null). | join, card |
| `streams.watch.registration-required` | Join → `{outcome:"registration_required", card, entry:null}`. | "Нужен аккаунт" + "Эта трансляция открыта только для зарегистрированных." + button "Войти в Whisperer". | join |
| `streams.watch.not-live` | `outcome:"not_live"`. | "Эфир ещё не начался" + "Оставьте вкладку открытой — страница обновится…". The page does **not** actually poll; this state is static. | join |
| `streams.watch.ended` | `outcome:"ended"`. | "Эфир завершён" + "Трансляция закончилась. Ниже — переписка зала, если ведущий её сохранил." | join |
| `streams.watch.ended.archive` | Ended + `card.chat_archived:true` + archive GET returns messages. | Bordered box with "Чат" label and messages (max-h 320, scrolls). | archive |
| `streams.watch.waiting` | `outcome:"wait"`, `knock_token` set (or `sessionStorage` already holds one). | "Ждём, пока вас впустят" + "Ведущий получил вашу заявку…" + spinner + button "Отменить". | knock poll every 3s |
| `streams.watch.waiting.cancelled` | Click "Отменить". | Falls to the infinite spinner (outcome `"wait"` with no entry). | |
| `streams.watch.denied` | Knock GET returns 403. | Error strip "Ведущий отклонил заявку" + "Вход на эту трансляцию закрыт." | knock |
| `streams.watch.live.connecting` | `outcome:"audience"\|"stage"` with an `entry`. SFU not yet connected. | `.vroom`, stage spinner. Desktop chip `.vroom-chip` with the megaphone icon and `initialTitle`. Dock: "Чат", "Реакции" and "Поднять руку" appear once `/state` loads; red "Выйти". | state, chat, LiveKit |
| `streams.watch.live.no-speakers` | Connected, no stage member connected. | Megaphone + "Ждём спикеров в эфире". | SFU |
| `streams.watch.live.stage-grid` / `.spotlight` / `.presentation` | `stage.mode` from state or event, with connected members. | Grid of `.vroom-tile`, or large tile + 120px strip. | SFU |
| `streams.watch.live.viewers` | `state.viewers` is a number. | Chip suffix "· Зрителей: N". | state |
| `streams.watch.live.chat.*` | Desktop: open by default once `state` has loaded. Mobile: click "Чат". | Panel header "Чат". "Сообщений пока нет". Pinned header with pin icon. Stage-badge "спикер". Closed footers "Чат выключен ведущим" (`chat_mode:"off"`; the dock chat button also disappears). Input placeholder "Написать в чат…". | chat |
| `streams.watch.live.chat.failure` | Send POST error. | Red line: "Вы заблокированы в этом чате" (`detail:"chat_banned"`), "Слишком часто — подождите пару секунд" (429/`too_fast`), "Чат сейчас закрыт" (`{error:"chat_closed"}`), "Сообщение не отправлено". | send |
| `streams.watch.live.hand` | `requests_enabled:true` and not on stage. | `button[aria-label="Поднять руку"]`. Click → `aria-label="Опустить руку"` with `aria-pressed=true` (after state shows `my_request:"pending"`). | hand |
| `streams.watch.live.reactions` | `reactions_enabled:true` → click "Реакции". | `.vroom-pop` picker. | reactions |
| `streams.watch.live.on-stage` | `state.role:"speaker"\|"cohost"`. | Dock buttons "Включить микрофон", "Включить камеру", "Демонстрация экрана", leave `aria-label="Покинуть сцену"` (arrowDown icon). | SFU |
| `streams.watch.live.ended-by-host` | `state.status:"ended"` (GET or data event `{type:"ended"}`). | "Эфир завершён" + "Трансляция закончилась." + button "Обновить страницу". No card. | state |
| `streams.watch.left` | Viewer clicks `button[aria-label="Выйти"]`. | "Вы вышли из эфира" + "Трансляция продолжается без вас…" + "Вернуться в эфир" (reloads the page). | |

**Endpoints** (types in `features/streams/contracts/types.ts`). Separate axios instances `pub` (`/v1/streams`) and `live` (`/v1/streams/live`) do **not** go through the refresh interceptor.
- `POST /v1/streams/{token}/join` body `{name, lang}`, plus Bearer access token if present → `JoinResult` (:144: outcome/card/entry/knock_token). `StreamCard` :92, `StreamPass` :109.
- `GET /v1/streams/{token}` → `StreamCard`.
- `GET /v1/streams/knock/{knock}` → `JoinResult`, every 3s. A 403 means denied; any other error restarts the join.
- `GET /v1/streams/{token}/chat` → `ChatMessage[]` (:54). Ended page only.
- Live calls, all with `Authorization: Bearer <pass.token>`:
  - `GET /state` → `LiveState` (:120). No polling; refetched on room connect and after personal events. Note `refetchOnWindowFocus` is globally false.
  - `GET /chat` → `ChatMessage[]`
  - `POST /chat {text}` → `ChatMessage`
  - `DELETE /chat/{id}`
  - `POST /chat/pin`
  - `POST /reactions {emoji}`
  - `POST /hand` → `{status}`; `DELETE /hand`
  - `POST /stage/leave` → `StageState`
  - `POST /bans`
- LiveKit WS at `pass.url` (same paths as rooms). Events arrive on data-channel topic `"stream"`. If the connection fails there is **no error UI**: the stage spinner stays forever.

**Hazards**
- Join-name input `autoFocus` (caret).
- Knock polling every 3s.
- Reaction animation (Math.random).
- Personal events (invited/removed/banned) are stored but never rendered.
- Plural key `viewers` has only the base form in ru.

---

## /studio/:id (StudioPage: host console)
- Access `public`, outside the shell (`feature.ts:46`). Effectively needs the stream owner (cookie session).
- Stream creation is paid on the backend (calendar).
- Example: `/app/studio/5d1e…`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `streams.studio.loading` | Overview or pass pending. | Full-screen `svg.spin`. | overview, pass |
| `streams.studio.unavailable` | Either call fails (anonymous gets 401 → refresh fails; also 403/404/500). | "Стрим недоступен" + dark button "В календарь" (`StudioPage.tsx:59-65`). | |
| `streams.studio.off-air` | `overview.status` is `"scheduled"` (also shown for `"ended"`). | Yellow button "Начать эфир" above the dock; desktop chip with grey dot "Эфир не начат". Panel "Пульт" open by default on desktop. Stage spinner until SFU connects; then "На сцене пока никого" or tiles (offline members are dimmed placeholders). | |
| `streams.studio.on-air` | `live.status` or `overview.status` is `"live"`. | Chip with red dot "В эфире" (+ "· Зрителей: N"); red dock button `aria-label="Завершить эфир"`. | |
| `streams.studio.confirm-end` | On air → click "Завершить эфир". | `dialog[aria-label="Завершить эфир?"]` "Зрители увидят, что трансляция закончилась. Начать её заново будет нельзя." with buttons "Отменить" / "Завершить эфир". | end |
| `streams.studio.toasts` | Start/end succeed or fail. | "Эфир начался" / "Не удалось начать эфир" / "Эфир завершён" (then navigates to `/calendar`) / "Не удалось завершить эфир". | |
| `streams.studio.panel.*` | `button[aria-label="Пульт"]` (badge = admissions + requests). | Header "Пульт". Sections in order: "Зал ожидания · N" (buttons "Впустить"/"Отклонить"), "Просят слова · N" ("Дать слово"/"Отказать"), "Ссылка для зрителей" (input + "Скопировать" → "Скопировано", "Поделиться", hint), "Как показывать сцену" (segments "Сетка"/"Крупно"/"Показ экрана"), "На сцене · N" (row actions "Закрепить на сцене", "Выключить микрофон", "Выключить камеру", "Убрать из эфира"/"Вернуть в эфир", "Сделать со-ведущим", "Убрать со сцены"; labels "ведущий", "со-ведущий"), "Зал" (search "Найти зрителя…", empty "В зале пока никого", viewer rows with tags "гость"/"аккаунт"/"Pro"/"истёк"/country/lang/time and button "На сцену"; "Свободных мест на сцене нет" when full), "Правила эфира" (Чат select, Реакции / Просить слово / Только зарегистрированные / Принимать вручную / Сохранять чат switches, "Мест на сцене" number input). | see below |
| `streams.studio.panel.failure` | Any studio action fails. | Red box "Свободных мест на сцене нет" (`{error:"speaker_limit_reached"}`) / "Это действие не по вашей роли" / "Не удалось сохранить". | |
| `streams.studio.chat` | `button[aria-label="Чат"]`. Renders only after `/state` loads. | Same chat panel; moderators get hover buttons "Закрепить", "Удалить сообщение", "Заблокировать в чате", plus an unpin `aria-label="Открепить"`. | chat |
| `streams.studio.record.*` | Owner with storage quota (`overview.room_id`). | Same as `rooms.room.record.*`. | stats, recordings |
| reactions | The studio's reactions button sends "👏" directly (no picker). | Floating emoji. | |

**Endpoints**
- `GET /v1/me/streams/{id}` → `StreamOverview` (:74).
- `POST /v1/me/streams/{id}/token` → `StreamPass` (:109).
- `POST …/start` and `POST …/end` → `StreamOverview`.
- `PATCH /v1/me/streams/{id}` → `StreamSettings` (:29).
- Live calls (Bearer pass.token):
  - `GET /state`, `GET /chat`, chat mutations
  - `GET /audience?query=` → `Viewer[]` (:157)
  - `POST /stage/members`; `DELETE`/`PATCH /stage/members/{p}`; `POST …/mute` → `{muted}`
  - `PATCH /stage` → `StageState` (:22)
  - `POST /requests/{id} {accept}`, `POST /admissions/{id} {accept}`, `POST /bans`
- `GET /v1/me/storage/stats`; `GET/POST /v1/me/rooms/{room_id}/recording*`.
- LiveKit WS. On failure there is no error UI (spinner forever).

**Hazards**
- **`GET /v1/streams/live/audience` polls about every 300ms plus RTT for as long as the "Пульт" panel is mounted.** `AudienceSection`'s effect depends on the `studio` object, which is a fresh literal on every render, and `setAudience` re-renders each time (`ui/StudioPanel.tsx:273-276`, `hooks/useStudio.ts:88`). Stub this or expect constant traffic.
- Copied state times out after 1.8s.
- `formatDateTime` / `formatTime` depend on timezone.
- `.rise` and `.pop` animations.

---

## /storage (StoragePage)
- Access `auth`, inside the shell (`features/storage/feature.ts:60`). Nav audience is user, but admins can also open it.
- **Paywall:** Free users (`!isPaidActive`) see the locked page. Start (paid, but stats returns 403 `storage_requires_pro`) sees the "Pro and Max" banner. Only Pro/Max get the browser.
- `data-onboarding="storage-upload"` is the anchor for the onboarding tour.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `storage.locked.free` | `user.subscription.tariff.code:"free"` (or inactive/expired). No storage requests. | PageHeader "Файлы" (eyebrow "Студия", index "07") + banner "Нужна подписка" / "«Файлы» доступна только на платной подписке (Start, Pro или Max)…" + button "Перейти к тарифам". | none |
| `storage.locked.no-quota` | Paid, and stats returns 403 `{detail:"storage_requires_pro"}`, or stats `limit_bytes:0`. | Banner "Хранилище на Pro и Max" / "На вашем тарифе файлового хранилища нет…". | list, stats |
| `storage.browser.loading` | Paid; list pending. | Toolbar (h1 "Файлы", "Загрузить", "Новая папка", sort combobox "Сортировка", view buttons "Плитка"/"Список", search "Поиск файлов…") + bare `svg.spin`. Note: a Start user briefly sees this before the 403. | list, stats |
| `storage.browser.empty` | `GET list` → `[]`, no query. **A list error also renders this** (data undefined). | Dropzone card "Перетащите файлы или папку сюда", "Любые файлы: документы, фото, видео, архивы", "до X на файл" (once stats loaded), buttons "Выбрать файлы" / "Выбрать папку". | list |
| `storage.browser.search-empty` | Type in "Поиск файлов…" with no matches. | Toolbar only; content area blank (no message, no dropzone). | list?q= |
| `storage.browser.grid` | List has items (default view). | `.stor-grid` > `.stor-tile[data-storage-id]`. Shared items show `.stor-badge` (clip icon). | list |
| `storage.browser.list` | Click `button[aria-label="Список"]`. | `table` > `tr.stor-row[data-storage-id]` with size and date columns. | |
| `storage.browser.subfolder` | Click a folder tile (`.stor-tile-btn`). | Breadcrumb buttons "Файлы", "/ X"; h1 = folder name. | list?parent_id= |
| `storage.quota.normal` / `.danger` / `.over` | Stats `used/limit` below 90% / at least 90% / `over_limit:true`. | "{used} из {limit}" with a bar (`bg-foreground` vs `bg-destructive`); over adds "Хранилище переполнено — освободите место или обновите тариф". | stats |
| `storage.selection-bar` | Click `.stor-check` (`aria-label="Выбрать"`) on an item, or drag a marquee over empty space. | `.stor-selbar` "Выбрано: N" + "Снять выделение", "В Базу знаний", "Переместить", "Удалить". Tiles get `data-selected="true"`. | |
| `storage.marquee` | Pointer-drag of more than 5px on empty area. | Fixed `div[aria-hidden]` with `border-2 bg-primary/20`. | |
| `storage.drop-hover` | Drag OS files over the area. | Area gets the `shadow-[inset_0_0_0_2px_var(--y)]` class; dropzone switches to `border-foreground bg-primary/15`. | |
| `storage.drop-reading` | Drop a folder (while reading the tree). | Dropzone buttons disabled + spinner. | |
| `storage.upload-menu` | Click "Загрузить". | Context menu "Выбрать файлы" / "Выбрать папку". | |
| `storage.context-menu.file` / `.folder` / `.shared` | Right-click a tile, or `.stor-kebab` (`aria-label="Ещё"`, visible on hover). | File: "Открыть", "Скачать", "Поделиться", "В Базу знаний", "Переименовать", "Переместить", "Удалить". Folder: "Открыть", "Поделиться", …. Shared: "Закрыть доступ" instead of "Поделиться". | |
| `storage.dialog.new-folder` | Click "Новая папка". | Popover `dialog[aria-label="Новая папка"]`, field "Имя папки", buttons "Отмена" / "Создать". | POST folder |
| `storage.dialog.rename` | Menu → "Переименовать". | `dialog[aria-label="Переименовать"]` "Новое имя", buttons "Сохранить" / "Отмена". | PATCH |
| `storage.dialog.delete` / `.bulk-delete` | Menu → "Удалить" / selection bar "Удалить". | `dialog[aria-label="Удалить"]` "Удалить «X»?" / "Удалить выбранные (N)?". | DELETE / bulk-delete |
| `storage.dialog.move` / `.bulk-move` | Menu → "Переместить" / bar "Переместить". | `dialog[aria-label="Переместить «X»"]` / "Переместить: N"; folder rows `.stor-move-row`; empty "Нет вложенных папок"; buttons "Отмена" / "Переместить сюда" ("сюда" is disabled at the current location). | list (browse) |
| `storage.share.main` | Menu → "Поделиться". | Modal `dialog[aria-label="Ссылка на файл"]` (folders: "Ссылка на папку"), cards "Просмотр" / "Просматривать смогут все, у кого есть ссылка" and "Настройки безопасности", buttons "Скопировать", "QR-код", "Удалить" (disabled when no link exists yet). | |
| `storage.share.security` | Click "Настройки безопасности". | Back button (title "Назад"), password input "Пароль" ("Не короче 4 символов", or "Пароль установлен — введите новый, чтобы заменить" + "Убрать"), "Срок действия" select ("Без срока", "1 дн."…), "Действует до …", checkbox "Запретить скачивание", footer "Сохранить". | POST share |
| `storage.share.qr` | Click "QR-код". This creates the link if missing. | `svg[role=img][aria-label="QR-код"]` + "Скачать QR-код"; spinner while the lib loads; error "Не удалось построить QR-код". | POST share |
| `storage.share.toasts` | | "Ссылка скопирована", "Не удалось скопировать", "Настройки сохранены", "Не удалось сохранить настройки ссылки", "Ссылка удалена". | |
| `storage.viewer.loading` / `.error` | Click a file tile (or "Открыть"). | Full-height `dialog[aria-label="{file name}"]` with spinner / "Не удалось открыть файл". | content / download-url |
| `storage.viewer.code` | `.txt` / `.py` / `.json` etc. | CodeMirror editor + "Сохранить" (disabled until edited) + "Скачать". | GET content (text) |
| `storage.viewer.pdf` / `.image` / `.video` / `.audio` | By extension or MIME (`model/fileKind.ts`). | `<object type=application/pdf>` / `<img>` / `<video controls>` / `<audio controls>` pointing at the presigned URL. | download-url?inline=true + S3 |
| `storage.viewer.docx` / `.sheet` | `.docx` / `.xlsx`. | `.md-content` sanitized HTML. | GET content (arraybuffer) |
| `storage.viewer.no-preview` | Other types. | "Предпросмотр недоступен — скачайте файл". | |
| toasts | | "Не удалось выполнить действие с файлом — изменения отменены", "Отправлено в Базу знаний: N", "Пропущено: N — …", "За раз можно отправить не больше 20 файлов", "Не удалось отправить в Базу знаний", "Сохранено". | |

**Endpoints** (`features/storage/api/storage.ts`; types in `features/storage/contracts/types.ts`)
- `GET /v1/me/storage/list?parent_id=&q=` → `StorageItem[]` (:9)
- `GET /v1/me/storage/stats` → `StorageStats` (:31)
- `POST /v1/me/storage/folder` → `StorageItem`
- `POST /v1/me/storage/upload` (multipart) → `StorageItem`. Upload progress shows in the platform upload panel.
- `PATCH /v1/me/storage/{id}`
- `DELETE /v1/me/storage/{id}`
- `POST /v1/me/storage/bulk-delete`, `POST /v1/me/storage/bulk-move`
- `POST /v1/me/storage/knowledge` → `SendToKnowledgeResult` (:92)
- `POST /v1/me/storage/{id}/share` → `ShareResponse` (:42)
- `DELETE /v1/me/storage/{id}/share`
- `GET /v1/me/storage/download-url/{id}[?inline=true]` → `{url}` (download opens `window.open` with noopener)
- `GET /v1/me/storage/content/{id}` (text or arraybuffer); `PUT /v1/me/storage/content/{id}` → `StorageItem`

**Hazards**
- Dates in `formatDateTime` (Intl, timezone).
- Kebab and checkbox appear only on hover (opacity transitions 120ms).
- `.rise` animation.
- Native drag and drop; marquee.
- Optimistic mutations; toasts.
- Popover position follows the last cursor position (`useCursorAnchor`).
- `PromptModal` and `Input` focus.
- Embedded PDF, media, QR canvas.
- Lazy chunks for CodeMirror, mammoth, xlsx, qrcode.

---

## /s/:token (SharedFilePage: public shared link)
- Access `public`, outside the shell (`feature.ts:64`). Anonymous users are allowed.
- The module is in the main bundle; the folder view is lazy.
- The backend `/v1/storage/shared/{token}` redirects here (password-protected files, and always for folders).

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `shared.loading` | Meta pending. | `img[alt="Whisperer"]` (`/icon-512.png`) + card with spinner. | meta |
| `shared.gone` | Meta `{found:false}` or request error. | "Ссылка недействительна" + "Её отозвали или истёк срок действия" (red x icon). | meta |
| `shared.file.password` | `{found:true, is_folder:false, needs_password:true, name, size}`. Note the form shows for any non-folder, even without `needs_password`. | Shield icon, file name, size (mono), Input "Пароль от ссылки" (hint "Его сообщает тот, кто прислал ссылку", **autoFocus**), button "Скачать файл", or "Открыть файл" if `download_disabled`. Disabled while empty. | |
| `shared.file.wrong` | Unlock → `{ok:false}` or error. | Input error "Неверный пароль". | unlock |
| `shared.file.success` | Unlock → `{ok:true, url}`. | Navigates away (`window.location.href = url`). | unlock |
| `shared.folder.password` | `is_folder:true, needs_password:true`. | Folder icon + button "Открыть папку". | |
| `shared.folder.browsing` | Folder without a password, or after unlock → `{ok:true, ticket}`. | Wider card (760px), breadcrumb buttons (current one disabled and bold), table `tr.stor-row`; loading spinner; empty "Папка пуста"; failure shows the same "Ссылка недействительна". | list |
| `shared.folder.subfolder` | Click a folder row. | Breadcrumb "Root / Sub". | list?folder= |
| `shared.folder.expired` | List → `{found:false, needs_password:true}`. | Back to the password form. | list |

**Endpoints**
- `GET /v1/storage/shared/{token}/meta` → `SharedMeta` (:47)
- `POST /v1/storage/shared/{token}/unlock[?download=1]` body `{password}` → `{ok, url?, ticket?}` (`api/storage.ts:142`)
- `GET /v1/storage/shared/{token}/list?folder=&ticket=` → `SharedListing` (:67)
- File open: `window.open('/v1/storage/shared/{token}/file/{id}?download=1&ticket=')` (`model/urls.ts`)

**Hazards:** password `autoFocus` (caret), external `/icon-512.png`, `formatDateTime` (timezone), `.rise` animation.

---

## /tracker (ProjectsPage, under the pathless TrackerLayout `.trk`)
- Access `auth`, inside the shell (`features/tracker/feature.ts:58-65`).
- Any tariff, including Free.
- The onboarding tour step "tracker" targets the nav anchor.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `tracker.projects.loading` | List pending (also the layout Suspense). | h1 "Трекер" + `svg.spin`. | list |
| `tracker.projects.empty` | `GET projects?archived=false` → `[]`. **An error also renders this.** | `[data-slot=empty]` "Пока нет проектов" / "Создайте первый проект, чтобы начать доску." | list |
| `tracker.projects.populated` | Projects present. | `.trk-proj-card` with key badge, name, description, button "Открыть доску", kebab (title "Ещё"). | list |
| `tracker.projects.archived` | Click "Архив". | Button now reads "Активные"; list from `archived=true`. | list?archived=true |
| `tracker.projects.pending-card` | Just created (temporary id, before the POST resolves). | `.trk-proj-card[data-pending="true"][aria-busy="true"]`, button disabled. | POST |
| `tracker.projects.menu` | Right-click a card or click the kebab. | Menu "Открыть доску", "Изменить", "В архив" (or "Вернуть"), "Удалить". | |
| `tracker.project.modal.new` / `.edit` | "Новый проект" / menu "Изменить". | `dialog[aria-label="Новый проект"]` / "Редактировать проект"; fields "Название", "Код" (placeholder "WHS", hint "Латинские буквы и цифры, до 10 символов"), "Описание"; buttons "Отмена" / "Создать" ("Сохранить"). | |
| `tracker.project.delete-confirm` | Menu "Удалить". | Popover "Удалить проект «X» со всеми колонками, задачами и метками?". | DELETE |
| toast | Mutation error. | "Не удалось выполнить действие — изменения отменены". | |

**Endpoints**
- `GET /v1/me/tracker/projects?archived=` → `TrackerProject[]` (`features/tracker/contracts/types.ts:6`)
- `POST`/`PATCH`/`DELETE /v1/me/tracker/projects[/{id}]`
- Hovering or pressing a card prefetches `GET /v1/me/tracker/projects/{id}/board` (`staleTime` 30s).

**Hazards:** hover prefetch, `.rise` animation, card hover lift transition.

## /tracker/:projectId (BoardPage)
- Access `auth`, inside the shell. Any tariff.
- Example: `/app/tracker/8a2c…`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `tracker.board.loading` | Board pending. **A board error (404/500) also stays as an infinite spinner.** | `svg.spin` only. | board |
| `tracker.board.populated` | Board with statuses and tasks. | Back link `a[aria-label="Проекты"]`, key badge, h1 name, Jira chip, search `aria-label="Поиск задач"`, priority combobox "Все приоритеты", button "Добавить колонку", `.trk-board` > `.trk-col` > `button.trk-card[aria-label=title]` with priority dot, label pills, due date. | board, jira status |
| `tracker.board.empty-column` | A column with no tasks, or none matching the filter. | "Нет задач". | |
| `tracker.board.filtered` | Type in search or pick a priority. | Fewer cards. | |
| `tracker.board.task-menu` | Right-click a card. | Menu "Изменить", "Низкий"/"Средний"/"Высокий"/"Срочный" (current one has a check icon), "Удалить". | |
| `tracker.board.column-menu` | Kebab `title="Действия с колонкой"`, or right-click a column. | "Добавить задачу", "Переименовать колонку", "Удалить колонку". | |
| `tracker.board.task-modal.new` / `.edit` | Column "+" (`title="Добавить задачу"`) / click a card. | `dialog[aria-label="Новая задача"]` / "Задача"; fields "Название", "Описание", selects "Колонка" and "Приоритет", date "Срок", labels ("Меток пока нет", input "Новая метка" + "Добавить"); edit adds a red "Удалить". | |
| `tracker.board.status-modal.new` / `.edit` | "Добавить колонку" / menu "Переименовать колонку". | `dialog[aria-label="Новая колонка"]` / "Переименовать колонку"; "Название", "Категория", color input "Цвет". | |
| `tracker.board.delete-confirm` | Task menu "Удалить". | "Удалить задачу «X»? Это действие необратимо." | |
| `tracker.board.column-delete-error` | Delete a non-empty column, or the last one. | Toast "Нельзя удалить колонку: сначала перенесите…". | DELETE status |
| `tracker.board.drag` | Native drag of a card. | `.trk-col[data-over="true"]`, `.trk-card[data-dragging="true"]`. | POST move |
| `tracker.board.pending` | Optimistic task or column. | `[data-pending="true"]`. | |
| `tracker.jira.chip.unlinked` / `.linked` / `.failing` | Jira status `project_key` null / set / set + `last_error`. | Ghost button "Jira" / button with the key and a yellow (live) or grey dot, title "Синхронизируется с проектом KEY" / danger button with flag icon, title "Синхронизация с KEY не удалась". The chip is quiet on error and shows "Jira". | jira status |
| `tracker.jira.modal.loading` / `.connect` / `.choose` / `.linked` | Click the chip. | `dialog[aria-label="Синхронизация с Jira"]`. Loading spinner. Connect: "Подключите Atlassian…" + "Подключить Atlassian". Choose: "Подключено: acc", "Инстанс Jira" (only with more than 1 site), "Проект Jira" placeholder "Выберите проект" or "Загружаем…", "Связать". Linked: key, "Обновления приходят сразу" or "…раз в несколько минут", "Последняя синхронизация: …" / "ещё не было", red error box, "Обновить сейчас", "Отключить". | jira * |
| toasts | | "Проект связан. Первая синхронизация идёт в фоне.", "Получено N, отправлено M", plus error texts "Доступ к Atlassian истёк — подключите заново." etc. | |

**Endpoints** (`features/tracker/api/index.ts`, `features/tracker/api/jira.ts`)
- `GET /v1/me/tracker/projects/{id}/board` → `TrackerBoard` (:47)
- `POST …/projects/{id}/tasks`, `PATCH /tasks/{id}`, `POST /tasks/{id}/move`, `PUT /tasks/{id}/labels`, `DELETE /tasks/{id}`
- `POST …/projects/{id}/statuses`, `PATCH /statuses/{id}`, `DELETE /statuses/{id}`, `POST …/statuses/reorder`
- `POST …/projects/{id}/labels`
- `GET /v1/me/jira/links/{projectId}` → `JiraStatus` (:79)
- `POST /v1/me/jira/authorize` → `{authorize_url}` (navigates to Atlassian)
- `GET /v1/me/jira/sites` → `JiraSite[]` (:95)
- `GET /v1/me/jira/projects?cloud_id=` → `JiraProject[]` (:101)
- `POST /v1/me/jira/links`, `DELETE /v1/me/jira/links/{id}`
- `POST /v1/me/jira/links/{id}/sync` → `JiraSyncResult` (:107)

**Hazards**
- Due dates use `toLocaleDateString()` (browser locale and timezone); Jira `last_sync_at` uses `toLocaleString`.
- Drag and drop (zustand `boardDrag`).
- Horizontal scroll on `.trk-board`.
- Optimistic temporary ids.
- Modal `.pop` animation; ContextMenu position comes from the click.

---

## Redirect-only routes
- `/rooms` → `/calendar` (`features/calendar/feature.ts:27`, access `auth`, inside the shell).
- `TrackerLayout` is a pathless layout route, not a redirect.
- No other redirects exist in these four features.
- `/meet/<token>` is a backend route (`backend/web_meeting.py`), not the SPA.

## Cross-cutting notes
- **SFU dependence**: these states need a real (or emulated) LiveKit connection:
  - rooms: participant tiles, the whiteboard, chat/reaction delivery, subtitles WS, device lists;
  - streams: stage tiles and data events.
- **Reachable over HTTP alone** (block or fail the LiveKit WS so the page stays "connecting" or "error"):
  - rooms: the dock, chat/translator/AI panels, reactions picker, "Ещё" menu, invite modal, record button, AI Q&A;
  - streams: the dock, chat panel, hand button, studio panel.
- Room HUD error text exists only in rooms. Streams pages have no SFU error UI.
- **Separate axios clients** (`/v1/subtitles`, `/v1/whiteboard`, `/v1/meeting-ai`, `/v1/streams`, `/v1/streams/live`) authenticate with the **room/stream pass** as Bearer and skip the refresh and network-overlay interceptors. Only the `/v1` `api` client triggers `/v1/auth/refresh` on 401.
- **Paywall summary:**
  - Storage: Free sees the locked page; Start sees "Хранилище на Pro и Max"; Pro/Max get full access.
  - Room/stream recording: Pro/Max (stats `limit_bytes>0`).
  - Room AI: host Start/Pro/Max, server flag `ai_assistant`.
  - Subtitles: server errors `subtitles_subscription_required`, `_quota_exhausted`, `_premium_budget_exhausted`.
  - Tracker and rooms are free.
  - `/admin/livekit` is admin only.
- **Bugs / misleading states to know about:**
  - The guest waiting/registration/denied responses have no UI.
  - Stream join failure with a working card spins forever; "Отменить" in the waiting room also leads to an infinite spinner.
  - A storage list error renders the empty dropzone.
  - A tracker projects error renders the empty state; a board error spins forever.
  - A LiveKit admin health request failure shows "SFU в норме".
  - The studio audience request loops about every 300ms.
  - A Start user briefly sees the full storage UI before the 403 lock.
- **Global hazards:**
  - `.rise` (360ms), `.pop` (180ms), `.spin`, `.pulse-y` animations (`shared/styles/globals.css:500-546`).
  - Toaster (`role=status`/`alert`, auto-dismiss with an animated progress bar).
  - `isPaidActive` compares `expires_at` with `Date.now()`.
  - `formatDateTime`/`formatTime` use Intl in the current timezone.
  - i18n namespaces load lazily (`useSuspense:false`). Streams pages use the `rooms` namespace, which is not preloaded by `lazyScreen("streams")`, so expect a possible raw-key first frame.
  - Popovers (ConfirmModal, PromptModal, MoveModal) are positioned at the last pointer location.
  - ContextMenus close on scroll/resize.
  - `useIsMobile` breakpoint is 860px and changes dock/panel layouts.
  - The onboarding tour can overlay `/tracker` and `/storage` (`features/onboarding/contracts/steps.ts:86-88`).

### Findings (step 6 of D2)

Draft defects visible on screen. By decision 4 of the D2 plan they stay out of the baseline, and v2 shows the intended behaviour.

1. **Guest join outcomes without a screen.** For `registration_required`, `admission_denied` and `{status:"waiting"}` the guest page draws the pre-join form again with no message (`GuestJoinPage`: only `finished` and `unavailable` have text). For "waiting" it also never polls: the knock URL it would use, `GET /v1/rooms/knock/{token}`, is not a backend route. Contract note: the draft backend never sends these three outcomes on the rooms endpoints; they belong to streams. Out of the baseline: `rooms.guest.registration`, `.denied`, `.waiting`.
2. **The stream viewer page spins forever.** When the join request fails but the stream card loads (for example a 403 on a members-only stream), and after «Отменить» in the waiting room, the page shows only the full-screen spinner (`card` set, `entry` and `outcome` empty). Out of the baseline: `streams.watch.stuck-spinner`, `streams.watch.waiting.cancelled`.
3. **A storage list error looks like an empty folder.** A failed `GET /v1/me/storage/list` renders the drop zone «Перетащите файлы или папку сюда», as for a folder with no files. Out of the baseline; v2 shows an error.
4. **Tracker errors look like data.** A failed projects list renders «Пока нет проектов»; a failed board request keeps the spinner forever. Out of the baseline; v2 shows an error.
5. **LiveKit health failure reads as healthy.** When `GET /v1/admin/livekit/health` fails, the page shows the tag «SFU в норме» with no metrics and no sections (`health` undefined is treated as "not down"). Out of the baseline: `livekit.health.request-failed`.
6. **The LiveKit admin page is not translated.** All texts of `/admin/livekit` are hard-coded in Russian (`features/rooms/admin/*.tsx`), so an English admin sees Russian. `livekit.*` is captured in ru cells only.
7. **The studio re-requests the audience without pause (contract and performance note, not a screen).** While «Пульт» is open, `GET /v1/streams/live/audience` repeats about every 300 ms plus the round trip: the effect in `AudienceSection` depends on an object that is new on every render (`ui/StudioPanel.tsx:273-276`, `hooks/useStudio.ts:88`). The harness answers the first request and holds the rest. v2 refreshes the hall on events or a fixed interval.
8. **A Start user briefly sees the full storage screen.** Before `GET /v1/me/storage/stats` answers 403, a paid Start user sees the toolbar and the browser, then the «Хранилище на Pro и Max» banner replaces them. The baseline captures the settled banner (`storage.locked.no-quota`); v2 decides access before drawing the browser.

### Coverage in the screenshot matrix (step 6 of D2)

**How the harness reproduces this group:**
- **Media server.** The recording API runs with fake LiveKit keys (`compose.yaml`): tokens and stream passes are signed locally, so room and stream entry record for real. The browser's socket to `wss://livekit.parity.localhost` is closed by the harness, and the room stays in «Не удалось подключиться». The dock, panels, menus and dialogs draw over HTTP and are captured in that state. `rooms.room.connecting` keeps the socket open and silent instead.
- **Camera and microphone.** Chromium's fake devices give a granted preview; its moving test picture is masked. `mediaAccess` on a state makes `getUserMedia` reject (`denied`) or never settle (`permission-pending`) (`src/determinism/media-access.ts`).
- **Speech recognition.** The Web Speech API is replaced by a silent recogniser (`src/determinism/page-setup.ts`): the AI assistant shows «Транскрипция идёт» with no lines and sends nothing to Google.
- **Stream viewer storage.** The guest name lives in localStorage (`wh.stream.name`, recorded with the visit) and the knock token in sessionStorage (`session` on the visit and on the state).
- **Viewer count.** `record.sh` writes `stream:viewers:r-parity-live` to Redis after the flush (`recording/seed/redis.txt`), so the count is recorded, not synthetic.
- **Files without S3.** The recording stand has no S3, so the draft answers previews with an empty body or a 500. File content is set by the state:
  - text and code — the `content` response as text;
  - DOCX and XLSX — the `content` response as bytes (`bodyEncoding: "base64"`), built in memory by `src/samples/office.ts`;
  - image and PDF — a synthetic `download-url` that points at a stand-in object store, `http://objects.parity.localhost` (`src/serve/object-store.ts`, samples from `src/samples/images.ts`);
  - video and audio — the same, but the object is absent: the harness browser has no H.264 or AAC decoders, so both targets show an empty player and only its frame is compared.
- **Harness browser limits, the same for both targets.** Chromium headless shell has no built-in PDF viewer, so `storage.viewer.pdf` shows the fallback text of `<object>`. Native date fields (`<input type=date>`) format dates by the browser build (mm/dd/yyyy), not by the page locale.
- **Recorded refusals.** Deleting a column with tasks (422 with the draft's text), a wrong share password and the share folder unlock are recorded by the visits.
- **Synthetic responses.** Each has a reason: LiveKit health, load, participants and egress; recording start and stop; the meeting assistant's answers; Atlassian sites, projects and sync; file content and signed URLs; share links minted with a random token; the stream audience.

**Captured inside another state:**

| state | screenshot |
|---|---|
| `rooms.room.record.idle` | `rooms.room.connect-error` (the record button is in the dock) |
| `rooms.room.connected.e2ee` without record and AI | `rooms.room.e2ee`, `rooms.room.more-menu.e2ee` |
| mobile record menu item, mobile dock | `rooms.room.more-menu.mobile`, the mobile cells of `rooms.room.connect-error` |
| `rooms.prejoin.mobile` | the mobile cells of `rooms.host.signin-required` and `rooms.prejoin.granted` |
| `rooms.guest.prejoin` permission variants | `rooms.prejoin.*` (the same component; the guest adds the name field) |
| `streams.watch.ended.archive` | `streams.watch.ended` |
| `streams.watch.live.connecting`, `.viewers`, `.chat.*` (desktop open by default) | `streams.watch.live.audience` |
| `streams.studio.panel.*` sections: waiting room, hands, link, layout, stage | `streams.studio.on-air` |
| `streams.studio.record.*` | `rooms.room.record.*` (the same control) |
| `storage.quota.normal` | `storage.browser.grid` |
| `storage.viewer.code` edited | `storage.viewer.save-error` (Save enabled after typing) |
| `storage.dialog.move` into a nested folder | `storage.dialog.move` (root level) |
| `tracker.board.empty-column` | `tracker.board.populated` (column «На проверке») |
| `tracker.jira.chip.linked` | `tracker.board.populated` |
| `livekit.rooms.populated`, `.egress.unavailable`, `.audit.populated` | `livekit.health.ok`, `livekit.audit` |

**Not screenshotted:**

| state | reason |
|---|---|
| `rooms.room.connected.*`, `.layout.*`, `.tile.*`, `.chat.populated`, `.chat.unread-badge`, `.reaction-floating`, `.device-menu`, `.subtitles-overlay`, `.translator.listening`, `.ready`, `.failure-*`, `.notepad`, `.board.*`, `.board-saved-toast` | need a connected SFU, its data channel or the subtitles socket (decision 3 of the D2 plan) |
| `streams.watch.live.no-speakers`, `.stage-grid`, `.spotlight`, `.presentation`; stage tiles in the studio | need a connected SFU (decision 3) |
| `rooms.room.ai.saved`, `.save-error` | need transcript lines from live speech recognition |
| `rooms.guest.registration`, `.denied`, `.waiting` | Finding 1 |
| `rooms.guest.redirect-stream` | the server sends the guest to the backend page `/live/<token>`, not to the SPA |
| `streams.watch.stuck-spinner`, `.waiting.cancelled` | Finding 2 |
| storage list error, tracker projects and board errors | Findings 3 and 4 |
| `livekit.health.request-failed` | Finding 5 |
| `en` cells of `livekit.*` | Finding 6 |
| `rooms.room.invite-modal.copied`, `storage.share` copy toasts, studio «Скопировано» | need clipboard permission and live 1.8 s on a real timer |
| `storage.marquee`, `storage.drop-hover`, `storage.drop-reading`, `tracker.board.drag` | intermediate frames of a pointer or file drag; the harness captures settled screens |
| `shared.file.success` | navigates away to the signed S3 URL |
| `streams.studio` start and end success toasts | the screen after a start is `streams.studio.on-air`; ending navigates to `/calendar` |
| `tracker.jira.modal.loading` | the chip that opens the modal appears only after the status has loaded, and the modal reuses it |
| `tracker.jira` link and sync error toasts | the same toast component as `tracker.jira.toast.synced` with another text |
