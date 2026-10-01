> Draft commit `589917e847f7d7213b3af5a3959bcc88c7500fe7`, read on 2026-10-01. File paths and line numbers refer to `/root/whisperer/frontend` at that commit.

# UI state inventory: leo, prompts, models, mcp, hub

Root: `/root/whisperer/frontend`. Router basename is `/app` (`src/app/main.tsx:48`), so every path below is shown without it. The browser URL is `/app` + path. Axios base is `/v1` (`src/shared/api/client.ts:30`). SSE and WebSocket calls use absolute `/v1/...` URLs and bypass axios. RU strings come from `src/features/<f>/locales/ru.json`. Platform strings come from `src/locales/ru/common.json` and `src/locales/ru/errors.json`.

**What the access levels mean** (`src/app/router/guards.tsx`):
- `auth`: any session. The check comes only from `RequireAuth` around `AppShell` (`src/app/App.tsx:89-97`).
- `user`: the session must not be admin. An admin is redirected to `/dashboard` (`guards.tsx:33-37`).
- `admin`: a non-admin is redirected to `/analytics` (`guards.tsx:26-30`).
- Paid means `isPaidActive(user)`: `subscription.status==="active"`, `tariff.code!=="free"` and not expired (`src/shared/entitlements/subscription.ts`).

**Shared selector facts:**
- `Modal` renders `<dialog aria-modal="true" aria-label={title}>` (`src/shared/ui/Modal.tsx:74-77`).
- `Popover`, `ConfirmModal` and `PromptModal` render a non-modal `<dialog class="pop …" aria-label={title}>` (`Popover.tsx:74-84`, `ConfirmModal.tsx`, `PromptModal.tsx:36`).
- `ContextMenu` is a portal `div.pop.fixed.z-[130]` with no role (`ContextMenu.tsx:87`).
- `IconButton` sets `aria-label` equal to `title` (`IconButton.tsx:17-18`).
- `Switch` is `button[role=switch][aria-checked][aria-label]` (`Select.tsx:387-391`).
- `Select` is a Radix combobox with `aria-label={ariaLabel}`. Its list portals into the nearest `<dialog>`.
- `Checkbox` is `input[type=checkbox][aria-label]`.
- `SegmentedToggle` buttons carry `aria-pressed` (`SegmentedToggle.tsx:37`).
- `Spinner` is `svg.spin` with no role (`Spinner.tsx:3`).
- `PageHeader` has `[data-onboarding="page-header"]` plus an `h1` (`PageHeader.tsx:27,37`).
- `HelpTip` is a button whose aria-label is the help text; on hover or focus it shows `[role=tooltip]`.
- Toasts use `role=alert` (error) or `role=status` (`Toaster.tsx:34`).

---

## Leo chat widget (shell slot, no route): host `/analytics`

**Access and mounting:**
- The widget is mounted by `leoFeature.shellSlots` (`src/features/leo/feature.ts:21`) into `AppShell` on every inside-shell route (`src/app/shell/AppShell.tsx:204-206`).
- It is absent on outside-shell routes, e.g. `/connect/mcp`.
- It appears for free, paid and admin users alike.
- It is remounted per user via `key={userId}` (`ui/LeoChatSlot.tsx:13-16`).
- Host route is `/analytics`, the user home. Use `/hub/<uuid>` for the hub-scope state.

**Free-user branch:**
- There is no paywall UI in the widget.
- The mic and voice buttons are hidden when `user.features.voice === false`. The server computes this flag; on Free it is false (`ChatComposer.tsx:82,229-240`).
- Sends go to the server. Any 4xx/402 comes back as the error bubble (see `leo.chat.error.http`).

**Deterministic seeding, recommended over replaying streams:**
- Messages: localStorage `agent-chat-v1:<user.id>` holds a `WidgetMessage[]` (`hooks/useChatPersistence.ts:14,36`). The thread id lives in `agent-session-v1:<user.id>` (`:16`).
- `loadMessages` does no transformation. A seeded `pending:true`, `actionStatus:"proposed"` or `steps` value renders as-is on first paint. Persistence then rewrites storage with proposals turned to `expired` and pending messages dropped (`:79`).
- Images are not stored in localStorage. They live in IndexedDB `whisperer-agent-images`, store `images`, keyPath `key` = `${userId}:${messageId}`, with fields `{key,userId,messageId,images:[{mime,data,alt}]}` (`store/imageStore.ts:20-31`). They are restored asynchronously.
- `WidgetMessage` shape: `contracts/chat.ts:16`. `ActionStatus` = `proposed|confirming|done|rejected|expired` (`chat.ts:14`).
- `ExecutionStep` = `{id,seq,status,activity,tool?,detail?,error?,startedAt,endedAt?,durationMs?}` (`contracts/progress.ts:53`).

### States: launcher, panel, layout

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `leo.launcher.closed` | Any shell page. Default `view:"closed"` (`ChatWidget.tsx:68`). | `button[aria-label="Открыть AI-ассистента"]` (round fixed button with SVG eyes, `ChatWidget.tsx:438-474`) | WS `/v1/ws/user` (always open) |
| `leo.launcher.voice-live` | Open panel → click `button[aria-label="Голосовой режим"]` → click `button[aria-label="Закрыть чат"]`. Voice keeps running while collapsed. | Launcher contains `span.pulse-y` with `bg-[var(--grn)]` (`ChatWidget.tsx:465-471`) | WS `/v1/ws/voice` |
| `leo.reminder-toast` | Panel closed. Server sends WS `/v1/ws/user` frame `{"type":"reminder.due","nudge_id":"n1","errand_id":"e1","turn_text":"Напоминаю: …","deliveries":{"web":"d1"}}`. TTL 90 s (`useReminderNotifications.ts:8`). | Fixed card `div.rise.fixed` above the launcher with bold "Leo" plus `turn_text`. `button[aria-label="Закрыть чат"]` is present while the launcher is visible (`ui/ReminderToast.tsx:9-48`). | Client sends `{"type":"ack","delivery_id":"d1"}`. Then `POST /v1/proactive/nudges/{nudge_id}/voice` (blob), falling back to `POST /v1/proactive/reminders/{errand_id}/voice`, then `speechSynthesis` (`useReminderNotifications.ts:40-62`). Clicking the toast opens the panel. |
| `leo.panel.empty` | Click launcher with no messages (empty localStorage). | Text "Спросите что угодно." plus four buttons: "Подведи итоги моих встреч за неделю", "Посчитай, сколько времени заняли мои встречи за месяц", "Оцени мою активность за месяц", "Назови мои последние встречи и их статусы". Hint "Наберите «@», чтобы указать встречу, хаб, задачу или файл." (`ChatWidget.tsx:525-561`) | none (`POST /v1/ai/agent/prewarm` on first textarea focus) |
| `leo.panel.fullscreen` | Desktop >860px. Click `button[aria-label="На весь экран"]`. | `button[aria-label="Свернуть"]` in the black header. Panel is `fixed inset-0`. Suggestions appear as a 2×2 grid (`.grid-cols-2`) (`ChatWidget.tsx:326-332,544`). | – |
| `leo.panel.mobile-sheet` | Viewport ≤860px (`useMediaQuery.ts:22`), open panel. | Full-screen sheet with no fullscreen toggle. Only "Новый диалог" and "Закрыть чат" are in the header. | – |
| `leo.panel.hub-scope` | Open panel on `/hub/3fa85f64-5717-4562-b3fc-2c963f66afa6`. The path must be a UUID (`hub/contracts/scope.ts:34`). | Bar "Отвечаю только по этому хабу" above the composer (`ChatWidget.tsx:385-390`). Hidden in voice mode. | `hub_id` is sent in the chat payload |
| `leo.panel.list-loading` | Messages exist and the lazy `ChatMessageList` chunk is not loaded yet (transient). | `svg.spin` centered in the scroll area (`ChatWidget.tsx:362-368`) | – |
| `leo.panel.new-chat` | Click `button[aria-label="Новый диалог"]`. | Returns to `leo.panel.empty`, with a new session id (`ChatWidget.tsx:177-182`). | – |

### States: conversation content (seed via localStorage)

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `leo.chat.populated` | Seed `[{id:"u1",role:"user",content:"Привет"},{id:"a1",role:"assistant",content:"Здравствуйте!"}]` → open panel. | User bubble `div.bg-foreground.whitespace-pre-wrap`; assistant bubble `div.md-content`; under the last assistant message, `button[aria-label="Копировать"]` and `button[aria-label="Повторить ответ"]` (`ChatMessageList.tsx:188-200`). | – |
| `leo.chat.copied` | Click "Копировать". | Label changes to "Скопировано" for 1.4 s (`ChatMessageList.tsx:299-305`). | – |
| `leo.chat.markdown` | Assistant content with headings, lists, a GFM table and a link. | `.md-content table` inside `div.md-table-wrap`. Links get `target=_blank`. Markdown images become links titled "изображение" (`MarkdownMessage.tsx:63-91`). | – |
| `leo.chat.code` | Content with ```` ```ts\nconst a=1\n``` ````. | `div.md-code` > `.md-code-bar` > `span.md-code-lang` "ts" plus `button[aria-label="Скопировать"]` (`CodeBlock.tsx:98-108`). | Grammar is lazy-loaded. Plain text shows until it arrives. |
| `leo.chat.code-long` | Code block with more than 20 lines. | `pre.md-code-clipped` plus `button.md-code-more` "Показать полностью" (`CodeBlock.tsx:13,106-113`). | – |
| `leo.chat.math` | `$$E=mc^2$$` or `$x^2$`. | Rendered: `[role="math"].md-math`, plus `.md-math-block` for display math. Before MathJax loads, or if TeX fails to parse: `code.md-math-src` (`MathSpan.tsx:33-46`). | – |
| `leo.chat.mermaid` | ```` ```mermaid\ngraph TD\nA-->B\n``` ```` (needs at least 2 non-empty lines). | `div.md-code.md-diagram .md-mermaid svg[id^="wh-mermaid-"]` plus toggle button "Код" (`MermaidBlock.tsx:66-83`). While the engine loads, or on a parse error, a CodeBlock with lang "mermaid" is shown instead. | – |
| `leo.chat.mermaid-source` | Click "Код" on the diagram. | Button text becomes "Диаграмма"; a `<pre><code>` shows the source. | – |
| `leo.chat.youtube` | Assistant (non-pending) text containing `https://youtu.be/<id>`. | `figure` containing `button[aria-label="Смотреть"]` over `img[src^="https://i.ytimg.com/vi/"]`, plus link "Открыть на YouTube" (`ChatMessageList.tsx:208-211,265-271`; `shared/markdown/ui/YouTubeEmbed.tsx`). | External thumbnail |
| `leo.chat.youtube-playing` | Click "Смотреть". | `iframe[src^="https://www.youtube.com/embed/"]` | External |
| `leo.chat.image` | Seed IndexedDB images for message `a1`, or replay SSE `image`. | `figure img[alt="Картинка, нарисованная Leo"]` (or a custom alt) plus link "Сохранить" with `download="leo-картинка.png"` (`ChatMessageList.tsx:89-127`). | – |
| `leo.chat.attachments-sent` | Seed a user message with `attachments:["отчёт.pdf"]` (content may be empty). | Chip with file icon and name under the user message. No empty bubble when content is "" (`ChatMessageList.tsx:238-250`). | – |
| `leo.chat.ledger-done` | Seed assistant `steps:[{id:"s1",seq:1,status:"completed",activity:"meetings",startedAt:1759300000000,endedAt:1759300004200,durationMs:4200}]`. | `[role=group][aria-label="Ход работы"]` with button "Готово за 4,2 с" and `aria-expanded="false"` (`ExecutionTimeline.tsx:198-223`). Routine-only activities (`analyzing,thinking,reviewing,composing,preparing`) collapse to nothing (`progressLedger.ts:192,202`). | – |
| `leo.chat.ledger-expanded` | Click the summary button. | `.leo-ledger-body[data-open="true"]` with `li.leo-step[data-status="completed"]` rows, e.g. "Ищу во встречах". Labels come from `model/toolLabels.ts:126-181`. | – |
| `leo.chat.ledger-failed` | Seed any step `status:"failed"`. | "Не всё получилось" with an x icon. Row detail "Не удалось", or "Слишком долго" when `error:"timeout"` (`ExecutionTimeline.tsx:88-96,211-213`). | – |
| `leo.chat.ledger-cancelled` | Stop mid-stream, or seed `status:"cancelled"`. | Row name has line-through. Detail "Отменено", or "Вы отклонили" for `error:"rejected"`. Quirk: the summary still reads "Готово за …" because only `failed` flips the summary text. | – |

### States: streaming (live SSE)

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `leo.chat.streaming.waiting` | Type in `textarea[aria-label="Сообщение AI-чату"]` and press Enter, or click a suggestion. Hold the stream open with no frames. | `li.leo-step[data-waiting="true"]` "Анализирую запрос" plus `button[aria-label="Остановить"]` in the composer (`ExecutionTimeline.tsx:248-264`; `ChatComposer.tsx:221-224`). No bubble is shown. | `POST /v1/ai/agent/chat` (SSE) |
| `leo.chat.streaming.steps` | Send `event: step` with `data: {"id":"s1","seq":1,"status":"started","activity":"meetings"}`. | `li.leo-step[data-status="started"] .leo-step-dot` "Ищу во встречах". A time column appears once ≥1.5 s have elapsed (ticks every second). After a running step closes, the waiting row reads "Продолжаю…". | same |
| `leo.chat.streaming.many-steps` | More than 5 steps while live. | `button[aria-label="Показать шаги"]` "+N" (`ExecutionTimeline.tsx:227-237`) | same |
| `leo.chat.streaming.tokens` | `event: token` / `data: {"text":"Привет"}`. | Growing `.md-content` bubble, no spinner. Copy controls stay hidden while pending. Render is throttled to 80 ms (`useThrottledValue.ts:6`). | same |
| `leo.chat.streaming.status-label` | Compatibility path: tokens arrive but no `step` events, plus `event: status` `data: {"phase":"tool","tool":"search_web"}`. | Under the text: `svg.spin` plus a label. Possible labels: "Ищу в интернете…", "Рисую…" (`generate_image`), "Смотрю ваши данные…", "Готовлю: {Название действия}" or "Готовлю действие…" (`phase:"action"`), or a raw server `label` (`ChatMessageList.tsx:59-68`; `toolLabels.ts:99-114`). | same |
| `leo.chat.stopped` | During streaming, click `button[aria-label="Остановить"]`. | Pending is cleared and open steps become cancelled. If no tokens or steps had arrived, the assistant row renders nothing (`useAgentChat.ts:185-198`). | Aborts the fetch |
| `leo.chat.error.stream` | `event: error` / `data: {"code":"stale_action","message":"…"}`. | Bubble "⚠️ Действие устарело — попросите агента ещё раз.". Known codes: `err_no_pending_action`, `err_secret_required`, `err_stale_action`. Otherwise the server `message`, otherwise "Что-то пошло не так. Попробуйте ещё раз." (`api/agent.ts:92-98`; `useAgentChat.ts:122-132`). | same |
| `leo.chat.error.http` | Respond with non-2xx JSON `{"detail":{"code":"…","message":"Нужна подписка"}}`. | Bubble "⚠️ {message}" (`api/agent.ts:101-109,154-159`). | same |
| `leo.chat.error.connection` | Drop the connection mid-stream. | Bubble "⚠️ Соединение прервано" (`errors:connection_lost`); steps close as failed. | same |
| `leo.chat.regenerating` | Click "Повторить ответ" on the last assistant message. | The last assistant message is replaced by a new pending one (waiting row). | `POST /v1/ai/agent/chat` with `regenerate:true` |

### States: action cards (`ActionCard.tsx:169-244`)

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `leo.chat.action.proposed` | Seed assistant `{content:"",action:{type:"action_proposal",name:"create_note",args:{summary:"Создать заметку",text:"…"},destructive:false,preview:null,needs_secret:false,secret_required:false,interrupt_id:"i1"},actionStatus:"proposed"}`, or SSE `event: action` / `data: {"action":{…}}`. | Card with uppercase header "Создать заметку" (`toolTitle`), title from `args.summary`, `<pre class="mono">` preview, buttons "Подтвердить" (yellow) and "Отклонить". | – |
| `leo.chat.action.destructive` | `destructive:true`, `preview:"Будет удалено: 3"`. | Red preview box. Warning "Действие необратимо — данные будут удалены.". Confirm button reads "Удалить" (danger). | – |
| `leo.chat.action.secret` | `needs_secret:true` with name `connect_integration`, `add_mcp_client` or other. | `input[type=password]` labelled "Токен или webhook-URL" / "Токен MCP-сервера (необязательно)" / "Секрет", plus hint "Агент не видит секрет — он уходит прямо на сервер.". When `secret_required:true` and the field is empty, confirm is disabled (`ActionCard.tsx:61-102,187`). | – |
| `leo.chat.action.batch` | `items:[…3 items]`. | Header "Действий: 3"; rows "1. …", "2. …". | – |
| `leo.chat.action.confirming` | Click "Подтвердить" and hold the `/act` stream open. | Confirm button shows `svg.spin`; both buttons are disabled. | `POST /v1/ai/agent/act` (SSE) |
| `leo.chat.action.done` | `/act` sends `event: action_result` / `data: {"ok":true,"status":"done","result":{"navigate_to":"/tracker"}}`, then `event: done` / `data: {}`. | Green "Выполнено". Epilogue tokens render as a second bubble under the card. `navigate_to` triggers navigation and opens the panel (`useAgentAction.ts:57-109`). | same |
| `leo.chat.action.rejected` | Click "Отклонить", then server sends `{"ok":false,"status":"rejected"}`. | "Отклонено" | `POST /v1/ai/agent/act` with `approved:false` |
| `leo.chat.action.expired` | Seeded proposal after a reload. Also reached on stream error or `status:"failed"` with nothing succeeded. | "Предложение устарело — попросите агента ещё раз.". Toast `role=alert` shows `error` (`useAgentAction.ts:67-75,157-160`). | – |

### States: composer, mentions, attachments, dictation, voice

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `leo.composer.empty` | Panel open with an empty field. | `button[aria-label="Добавить файл (до 5)"]`, `button[aria-label="Записать аудиосообщение"]`, `button[aria-label="Голосовой режим"]` (the last two only when `features.voice` is not false) | – |
| `leo.composer.free-no-voice` | User `/auth/me` returns `features.voice:false`. | Neither mic nor voice button exists. The empty field shows no right-side button. | – |
| `leo.composer.filled` | Type text. | `button[aria-label="Отправить"]` | – |
| `leo.composer.attachments` | Set files on `input[aria-label="Файлы вложения (до 5)"]`, e.g. `a.pdf`. | Chip with name plus `button[aria-label="Убрать вложение a.pdf"]` (`AttachmentChips.tsx`) | – |
| `leo.composer.attach-error` | More than 5 files, more than 10 MB, or a bad extension (e.g. `.exe`). | `div[role=alert]` with "Максимум 5 файлов за один запрос", "Суммарный размер вложений больше 10 МБ" or "Тип файла не поддерживается" (`ChatComposer.tsx:96-111,130-135`; limits `contracts/fileUpload.ts:7-15`) | – |
| `leo.composer.attach-full` | Exactly 5 files. | `button[aria-label="Достигнут лимит вложений (5)"][disabled]` | – |
| `leo.mention.loading` | Type `@ром`. After the 180 ms debounce the request is in flight. | `[role=listbox][aria-label="Объекты для упоминания"]` containing "Ищу…" (`MentionMenu.tsx:45-56`) | `GET /v1/me/search?q=ром&per_domain=3&domains=hubs,meetings,tracker,calendar,files` |
| `leo.mention.results` | Same request returns `{"hits":[{"domain":"hubs","id":"h1","title":"Ромашка","subtitle":null}]}`. | `[role=option][aria-selected=true]` "Ромашка" with kind label "Хаб" (others: "Встреча", "Задача", "Событие", "Файл"). Use ArrowDown/ArrowUp to move, Enter/Tab to pick, Escape to close. No results means no menu. | Response shape: `api/mentions.ts:18-23` |
| `leo.composer.recording` | Click "Записать аудиосообщение". | Canvas waveform, timer `span.mono` "00:00", buttons `[aria-label="Отменить запись"]` and `[aria-label="Готово"]` (`VoiceRecorder.tsx:182-194`) | getUserMedia |
| `leo.composer.dictating` | Click "Готово" with captured PCM. If the mic was denied there is no PCM and it returns to text immediately. | `textarea[disabled][placeholder="Распознаю…"]` and no send button | `POST /v1/ai/dictate` (multipart `audio`) → `{text}` (`api/agent.ts:254-261`) |
| `leo.composer.dictate-error` | Dictate returns 5xx. | Toast "Не удалось распознать запись" | same |
| `leo.voice.connecting` | Click "Голосовой режим". The WS opens; the server has not yet sent `ready`. | `div.mtg-cosmic.mtg-cosmic--connecting` with `output.mtg-cosmic-label` "Подключаю…" and `[aria-label="Выйти из голосового режима"]` (`VoiceMode.tsx:97-124`) | WS `/v1/ws/voice?sid=<session>` |
| `leo.voice.listening` / `.speaking` / `.consulting` | Server frames `{"t":"ready"}`, then `{"t":"phase","phase":"speaking"|"consulting"|"listening"}`; `{"t":"interrupted"}` returns to listening. | `.mtg-cosmic--listening` "Слушаю…", `.mtg-cosmic--speaking` "Отвечает…", `.mtg-cosmic--consulting` "Анализирую…" | same |
| `leo.voice.ended` | `{"t":"ended","reason":"user_closed"}` | `.mtg-cosmic--ended` "Завершено". Auto-returns to text after 2.5 s (`useVoiceMode.ts:6,27-31`). | same |
| `leo.voice.error.<code>` | `{"t":"error","code":"retry_later"|"voice_disabled"|"upgrade_required"|"minutes_exhausted"|"voice_error"}`, mic denied, or WS error. | `.mtg-cosmic--error` with label "Не удалось запустить голосовой режим. Попробуйте ещё раз через минуту." / "Голосовой режим временно недоступен." / "Голосовой режим доступен на любом платном тарифе." / "Исчерпан лимит минут — пополните тариф." / "Не удалось запустить голосовой режим." / "Нет доступа к микрофону. Разрешите доступ в браузере и попробуйте снова." / fallback "Ошибка" (`VoiceMode.tsx:67-77`) | same |
| `leo.voice.turn-in-chat` | `{"t":"turn","user":"…","assistant":"…"}` | Two new bubbles in the shared feed. `action` and `image` frames are buffered and appended after the turn (`useGeminiLive.ts:75-156`; `useVoiceChatSink.ts`). | same |
| `leo.reminder.deeplink` | URL `/cabinet/leo?reminder=<errand_id>` (any shell route works). | Panel opens with a new assistant bubble. The `reminder` query param is removed (`ChatWidget.tsx:244-265`). | `POST /v1/ai/agent/reminder-context` with `{session_id,errand_id}` → `{text}` |

**Things that do not exist in the code.** There is no model picker inside the chat; the Leo model is chosen at `/cabinet/leo` under "Модель Leo". There is no conversation-history list or thread switcher: one persisted thread exists, and "Новый диалог" resets it. Client actions `navigate` and `set_theme` render no card: they navigate, or switch the theme globally (`ChatWidget.tsx:195-212`).

### Endpoints and stream formats (Leo widget)

**Chat stream:** `POST /v1/ai/agent/chat` via `@microsoft/fetch-event-source` (`api/agent.ts:112-169`).
- Body is multipart. Field `payload` is JSON `{messages:[{role,content}], page, session_id, regenerate, hub_id, mentions:[{kind,id}]}`; files go in field `files`.
- Headers: `Authorization: Bearer`. `openWhenHidden:true`.
- Events are parsed in `dispatchEvent` (`api/agent.ts:39-80`). `data` must be valid JSON or the frame is dropped, so `done` needs `data: {}`.
  - `token` `{text}`
  - `status` `{phase:"tool"|"action",tool}` or `{mode,label}` (`AgentStatus`, `contracts/agent.ts:181`)
  - `step` `{id,seq?,status:"started"|"running"|"completed"|"failed"|"cancelled",activity,tool?,ts?,duration_ms?,detail?,error?}` (`AgentStepEvent`, `contracts/progress.ts:26`; validated in `model/progressLedger.ts:51-70`)
  - `image` `{mime?,data(base64),alt?}` (`AgentImage`, `agent.ts:164`)
  - `action` `{action:AgentAction}`, where `AgentAction` is navigate `{type:"navigate",to}`, `{type:"set_theme",theme}` or `AgentActionProposal` (`agent.ts:66-119`)
  - `action_result` (`AgentActionResultEvent`, `agent.ts:136`)
  - `error` `{code?,message?}`
  - `done`
- **Without `event: done` the message stays pending forever:** the stream ending only resolves the promise.

**Confirm stream:** `POST /v1/ai/agent/act`, JSON `{session_id,interrupt_id,approved,secret?}`, same SSE format (`api/agent.ts:180-215`).
- Tokens go into `epilogue`. `action` frames append new cards.
- `action_result` drives the final status (`useAgentAction.ts:57-109`). Without it, and without `error`, the card stays "confirming".

**Other REST calls:**
- `POST /v1/ai/agent/prewarm` (`:228`)
- `POST /v1/ai/agent/reminder-context` → `{text}` (`:242`)
- `POST /v1/ai/dictate` → `{text}` (`:254`)
- `GET /v1/me/search` → `{hits?:[{domain,id,title,subtitle}]}` (`api/mentions.ts:18-46`)
- `POST /v1/me/onboarding/progress` `{done_action:"first_question"}` after each successful `done`; skipped for admins (`useAgentChat.ts:120`; `onboarding/hooks/useOnboarding.ts:82-97`)
- `POST /v1/proactive/nudges/{id}/voice` and `POST /v1/proactive/reminders/{errandId}/voice` → WAV blob (`api/proactive.ts:28-42`)
- Push resync, only if localStorage `wh.push==="on"` and `Notification.permission==="granted"`: `POST /v1/proactive/push/devices`, or `GET /v1/proactive/push/key` → `{public_key}` (`usePushNotifications.ts:144-167`)

**Voice WebSocket:** `ws(s)://<host>/v1/ws/voice?sid=<sessionId>`, subprotocols `["whisperer-bearer", <accessToken>]` (`api/geminiLive.ts:11,51-56,74`).
- Server → client JSON text frames keyed by `t` (`geminiLive.ts:110-165`):
  - `ready`: client then calls getUserMedia and starts streaming
  - `audio` `{d}`: base64 PCM16 at 24 kHz, played by `PcmPlayer`
  - `transcript` `{speaker,text}`
  - `phase` `{phase}`
  - `interrupted`
  - `turn` `{user,assistant}`
  - `action` `{action}`
  - `image` `{mime,data,alt}`
  - `action_result`
  - `ended` `{reason}`
  - `error` `{code}`
- Client → server: `{"t":"audio","d":<base64 PCM16 16 kHz mono>}`.

**User-events WebSocket:** `ws(s)://<host>/v1/ws/user`, same subprotocol (`hooks/useUserEvents.ts:14-17,54`).
- On open the client sends `{"type":"hello","client":"web","chat_session_id":…}`, then `{"type":"ping"}` every 25 s.
- Reconnect backoff runs from 1.5 s up to 30 s.
- Server frames: `reminder.due` `{nudge_id,errand_id?,turn_text|body,deliveries:{web}}` and `reminder.settled` `{nudge_id}` (`:68-91`).

### Hazards (Leo widget)
- **Launcher eyes:** `LeoFace` follows the pointer through CSS vars `--leo-x/--leo-y` set from a global pointer listener plus rAF. It blinks on a 6.4 s infinite animation. Both are off under `prefers-reduced-motion` (`LeoFace.tsx:47-130`; `styles.css:216-245`).
- **Pulse dots:** `.pulse-y` (1.8 s infinite) runs on the header dot, the toast dot and the voice dot. Reduced motion does not stop it (`globals.css:527-531`).
- **Ledger:** clock ticks every second (`ExecutionTimeline.tsx:44-53`); times derive from `Date.now()` and client `startedAt`. Also `leo-step-in` 200 ms, `leo-step-pulse` 1.4 s infinite, and a 220 ms grid-rows transition.
- **Voice:** 41 wave bars with CSS animation (`.mtg-wave-bar`).
- **Recorder:** canvas drawn every rAF frame, with a `Math.random` fake waveform when mic access is denied (`VoiceRecorder.tsx:63`), plus a 1 s timer.
- **Lazy engines:** mermaid (dynamic import; SVG ids `wh-mermaid-N` with a global counter; 200 ms debounce while streaming), MathJax, and lowlight grammars. TeX or plain code shows until they load; wait for network idle.
- **External media:** YouTube thumbnail from `i.ytimg.com` (replaced if naturalWidth ≤120) and the youtube.com iframe.
- **Random ids:** message ids `m${n}_${Math.random}` (not visible). Session id from `crypto.randomUUID` appears in the WS URL and payload.
- **Persistent sockets:** `/v1/ws/user` stays open on every page with reconnect timers.
- **Media APIs:** AudioContext, getUserMedia, speechSynthesis, `new Audio`. Chime when a reminder toast appears.
- **Copy timers:** 1.4 s; the code-copy button behaves the same way.
- **Scroll:** stick-to-bottom on each update. The textarea auto-resizes up to 168 px.
- **Focus:** no `autoFocus`. Picking a mention focuses the textarea via rAF, which shows a caret.

---

## `/cabinet/leo`: the Leo tab of the cabinet modal

Route: `account` feature `/cabinet/:tab?`, access `user`, inside the shell (`src/features/account/feature.ts:44-46`).
- A direct URL renders `AnalyticsPage` underneath, with `CabinetModal` as `dialog[aria-modal][aria-label="Личный кабинет"]` on top.
- Visible only to **paid non-admin** users (`account/contracts/tabs.ts:27,47-49`).
- **Free user:** the "Leo" tab is absent from the nav; `/cabinet/leo` redirects to `/cabinet` ("Общие") (`account/pages/CabinetModal.tsx:91-93`).
- **Admin:** redirected to `/dashboard`.
- Tab button: `[data-onboarding="cabinet-tab-leo"]` "Leo".

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `leo.cab.loading` | Open `/cabinet/leo` while requests hang. | `.rise` cards each holding a centered `svg.spin` for personalization, connectors, initiative and errands. Memory and Capabilities render immediately (`LeoTab.tsx:1115-1123`; `LeoPersonalization.tsx:65-73`). | all below |
| `leo.cab.populated` | All requests OK. | Card headers "Персонализация", "Подключённые сервисы", "Инициатива", "Память", "Поручения", "Расширенные настройки" (`LeoTab.tsx:81-92`) | – |
| `leo.cab.model-select` | Click `[role=combobox][aria-label="Модель Leo"]`. The list holds only `type==="chat" && allowed!==false && enabled` models (`LeoPersonalization.tsx:155-200`). | Radix listbox with model display names. A spinner shows until configs and roles load. | `GET /v1/me/models/configs` (`CatalogModelOut[]`, `models/contracts/types.ts:61`); `GET /v1/me/models/roles` (`RoleAssignmentOut[]`, `:99`); `PUT /v1/me/models/roles/agent` |
| `leo.cab.personalization-saving` | Type in "Псевдоним", "Профессия" or "Пользовательские инструкции"; or change "Базовый стиль и тон" or a trait select ("Теплота", "Восторженность", "Заголовки и списки", "Эмодзи"). | "Сохраняем…" with spinner, then "Сохранено" for 2 s. The char counter appears near the limit (`LeoPersonalization.tsx:267-387`). Debounce 800 ms. | `GET`/`PUT /v1/personalization` (`Personalization`, `leo/contracts/settings.ts:139`); `PATCH /v1/me/profile` `{username}` |
| `leo.cab.connectors` | `/connectors` returns items with groups. | Group header (uppercase), then per card: connected = "Подключено" + "Отключить"; broken = "Доступ истёк — подключите заново" + "Переподключить"; neither = "Подключить" (`LeoTab.tsx:229-274`). | `GET /v1/connectors` → `{items:ConnectorCard[]}` (`settings.ts:16`) |
| `leo.cab.connector-connecting` | Click "Подключить". Opens popup `window.open(…,"whisperer-connect")`. | That card's button shows a spinner. Toast "Подключено" on success, "Не удалось начать подключение" on failure, "Браузер заблокировал окно авторизации — разрешите всплывающие окна для этого сайта" when the popup is blocked. | `POST /v1/connectors/session` `{provider}` → `ConnectSession` (`settings.ts:29`); `POST /v1/connectors/sync` → `{items}` |
| `leo.cab.connector-disconnect-confirm` | Click "Отключить". | `dialog[aria-label="Отключить сервис?"]` with message "Доступ будет отозван…" and buttons "Отмена" / "Отключить" | `DELETE /v1/connectors/{key}` |
| `leo.cab.initiative.<level>` | Click "Молчать", "Сдержанно" or "Активно" (the active level has a filled button). | Hint text, e.g. "Leo не пишет первым никогда.". With level `reserved`, the kinds "Подготовка к встрече", "Сервис отключился" and "В деле застряло" get the suffix " — только на уровне «Активно»" (`LeoTab.tsx:554-669`). | `GET`/`PUT /v1/proactive/settings` (`ProactiveSettings`, `settings.ts:93`) |
| `leo.cab.quiet-hours` | `quiet_enabled:true/false`. | `input[aria-label="Не беспокоить"]` checkbox; `input[type=time][aria-label="С"]` and `[aria-label="До"]` are disabled when off. | same |
| `leo.cab.mail-watches` | `/proactive/mail-watches` has items or is empty. | Rows with email, label and "Убрать"; inputs `[aria-label="Адрес"]` and `[aria-label="Кто это (тимлид)"]`; button "Следить" (`LeoTab.tsx:413-496`). | `GET /v1/proactive/mail-watches` → `{items:MailWatch[]}` (`settings.ts:175`); `POST` `{email,label}`; `DELETE ?email=` |
| `leo.cab.push` | Shown only when `/proactive/push/key` returns a non-empty `public_key`. | "Уведомления на устройстве", checkbox `[aria-label="Присылать на это устройство"]`. Hint depends on environment: "На iPhone и iPad…", "Этот браузер не показывает уведомления при закрытом приложении.", "Уведомления запрещены в настройках браузера…", or "Leo напомнит, даже когда приложение закрыто…". Devices line "Приходят на: …" (`LeoTab.tsx:510-545`). | `GET /v1/proactive/push/key`; `GET /v1/proactive/push/devices` → `{items:PushDevice[]}` (`settings.ts:84`) |
| `leo.cab.memory-off` | `user.memory_enabled:false`, or toggle `[role=switch][aria-label="Включить память"]`. | Hint "Память выключена: Leo не запоминает новое…" | `PATCH /v1/me/profile` `{memory_enabled}` |
| `leo.cab.memory-summary` | Click "Управление". | `dialog[aria-label="Сводка памяти"]` with "Обновлено {relative}", `button[aria-label="Обновить"]`, and the text parsed from `##` headings into bold lines (`LeoTab.tsx:782-916`) | `GET /v1/memory/summary` → `MemorySummary` (`settings.ts:117`) |
| `leo.cab.memory-summary.pending` / `.empty` / `.loading` | `{text:null,items:5}` / `{text:null,items:0}` / hanging request | "Сводка соберётся ночью. Не хотите ждать — нажмите «Обновить»." / "Пока пусто. Leo запоминает по ходу разговора — или скажите ему «запомни, что…»." / `svg.spin`. The ask input `[aria-label="Спросить или обновить"]` is disabled whenever there is no text. | same |
| `leo.cab.memory-answer` | Type a question, press Enter. | Answer pill with close `[aria-label="Отмена"]`. "Про это в памяти ничего нет." when `text:null`. | `POST /v1/memory/summary/ask` `{question}` → `{text}`; refresh via `POST /v1/memory/summary` |
| `leo.cab.memory-entries` | Click link "Сохранённые записи памяти (N)". | Nested `dialog[aria-label="Сохранённые записи памяти"]`. Rows show kind ("факт" / "разговор" / "привычка"), date, and "забыто" with opacity when `retention<0.15`, plus trash `[aria-label="Забыть"]`. Empty and loading variants exist. | `GET /v1/memory` → `{items:MemoryItem[]}` (`settings.ts:106`) |
| `leo.cab.memory-forget-confirm` | Click trash. | `dialog[aria-label="Забыть это?"]`, message is the item text, buttons "Отмена" / "Забыть" | `DELETE /v1/memory/{id}` |
| `leo.cab.errands.empty` / `.populated` | `/errands` returns `[]` or items. | "Пока пусто. Скажите Leo «напомни завтра в девять»…" / rows with summary, `toLocaleString` date, status "ожидает" / "выполнено" / "не получилось" / "отменено", red error text, and button "Отменить" only for scheduled errands (`LeoTab.tsx:278-364`) | `GET /v1/errands` → `{items:Errand[]}` (`settings.ts:46`) |
| `leo.cab.errand-cancel-confirm` | Click "Отменить". | `dialog[aria-label="Отменить поручение?"]` | `DELETE /v1/errands/{id}` |
| `leo.cab.capabilities` | Always rendered. | Four switches: "Поиск в интернете", "Голосовой режим", "Поиск в базе знаний", "Поиск в подключённых сервисах" (`LeoTab.tsx:1025-1078`) | `PATCH /v1/me/profile`, then `GET /v1/auth/me` |

**Error branch:** any failing GET leaves its block spinner showing forever (`if (isLoading || !data) return <BlockSpinner/>`). There is no error UI.

**Host endpoints:** `GET /v1/me` (billing cabinet, `refetchInterval:15000`, `CabinetSettings.tsx`), `GET /v1/me/referral`, plus all AnalyticsPage underlay endpoints when the URL is opened directly.

**Hazards:**
- Relative time "Обновлено …" uses `Date.now()` (`LeoTab.tsx:937-953`).
- Errand and memory dates use browser-TZ `toLocaleString` and `toLocaleDateString`.
- `.rise` 360 ms and `.pop` 180 ms animations are not disabled by reduced motion.
- 15 s polling of `/v1/me`.
- `window.open` popup with a 700 ms poll and a BroadcastChannel.
- Push hints depend on `Notification.permission`, `serviceWorker` support and UA.
- Autosave timers.

---

## `/cabinet/mcp`: the MCP tab of the cabinet modal

Route: `/cabinet/:tab?`, access `user`, inside the shell, paid non-admin only. **Free** users are redirected to `/cabinet`. Tab button: `[data-onboarding="cabinet-tab-mcp"]` "MCP" (`account/contracts/tabs.ts:32`). Component: `src/features/mcp/ui/McpTab.tsx:21-46`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `mcp.server.loading` | Default sub-tab "Сервер" while the request hangs. | `svg.spin` (`McpServerTab.tsx:77-91`). **Also shown forever on error.** | `GET /v1/me/mcp/server` → `McpServerConfig` (`mcp/contracts/types.ts:17`) |
| `mcp.server.populated` | Server config OK. | Toggle `button[aria-pressed=true]` "Сервер". Hint "Ваши данные → внешним AI: …". "Эндпоинт" field with button "Копировать". "Токен" masked as 24 "•". IconButtons `[aria-label="Показать"]`, `[aria-label="Копировать токен"]`, `[aria-label="Сгенерировать заново"]`. Section h2 "Что увидят AI-инструменты" with switches labelled by the server-provided `label`. | `PATCH /v1/me/mcp/server/resources/{key}` `{enabled}` |
| `mcp.server.token-revealed` | Click "Показать". | Raw token shown; button becomes "Скрыть". | – |
| `mcp.server.rotated` | Click "Сгенерировать заново". | Icon `animate-spin` while pending. Then the raw token shows, plus red "Токен показан один раз — скопируйте его сейчас. Позже отобразится только маска." | `POST /v1/me/mcp/server/rotate` → `McpServerConfig` |
| `mcp.server.copied` | Click "Копировать". | Yellow button "Скопировано" for 1.5 s (`McpServerTab.tsx:12-33`) | – |
| `mcp.client.empty` | Click toggle "Клиент"; clients list is `[]`. | Hint "Внешние данные → вашему AI: …", form fields "Название", "URL сервера", "Токен" (placeholder "необязательно"), button "Добавить", EmptyState "Внешних MCP-серверов пока нет" (`McpClientTab.tsx:34-168`). Errors also land here. | `GET /v1/me/mcp/clients` → `McpClientConnection[]` (`types.ts:29`) |
| `mcp.client.populated` | Clients with assorted `health` and `authKind`. | Row name, `HealthDot` text "работает" / "сбоит" / "недоступен" (nothing for `unknown`), URL. `authKind==="oauth2" && health!=="down"` shows green "Подключено". `health!=="ok"` shows button "Подключить". Switch `[aria-label="Активен"]`, trash `[aria-label="Удалить сервер"]`. | `PATCH /v1/me/mcp/clients/{id}` `{enabled}`; `DELETE /v1/me/mcp/clients/{id}` |
| `mcp.client.add-error` | Submit name and URL; server returns 422. | "Не удалось добавить сервер — проверьте URL." | `POST /v1/me/mcp/clients` `{name,url,token?}` (`McpClientInput`, `types.ts:44`) |
| `mcp.client.oauth-start` | Click "Подключить". | Button spinner, then a hard navigation to `authorizeUrl`. Toast "Не удалось подключить" on failure. | `POST /v1/me/mcp/clients/{id}/oauth/start` → `{authorizeUrl}` |
| `mcp.client.oauth-return` | `/cabinet/mcp?mcp_connect=ok` (or `error`), **then click "Клиент"**. The handler lives in `McpClientTab`, which does not mount on the default "Сервер" sub-tab (`McpClientTab.tsx:80-93`). | Toast "Подключён" or "Не удалось подключить". The query param is stripped. | `GET /v1/me/mcp/clients` (refetch) |

**Hazards:** 1.5 s copy timers, `.rise`/`.pop`, 15 s cabinet polling, external redirects (`window.location.assign`).

---

## `/settings/mcp`: redirect only
Access `auth`, inside the shell. Redirects to `/cabinet/mcp` and **keeps the query string** (`mcp/feature.ts:28`; `guards.tsx:48-52`). From there the `/cabinet` rules apply: free users go to `/cabinet`, admins to `/dashboard`.

---

## `/connect/mcp`: OAuth consent screen

Access is declared `auth` with `outsideShell:true` (`mcp/feature.ts:27`). There is no sidebar and no Leo widget.

**Finding:** no client-side auth gate is applied. `AccessGate` lets `auth` through (`guards.tsx:68-72`), and `renderRoutes(OUTSIDE_SHELL)` adds no `RequireAuth` (`App.tsx:88`). A logged-out visitor gets a 401 on the GET, the refresh fails, and the page shows the **error card**, not a login redirect. Any role (free, paid, admin) can reach the page.

Example URL: `/app/connect/mcp?client_id=c1&redirect_uri=https%3A%2F%2Fclaude.ai%2Fapi%2Fmcp%2Fauth_callback&code_challenge=abc&code_challenge_method=S256&response_type=code&scope=whisperer%3Ameetings.read%20whisperer%3Atracker.write&state=s1&resource=https%3A%2F%2Fwhisperer.one%2Fv1%2Fmcp`. Params are read once from `window.location.search` (`McpConsentPage.tsx:31-43`).

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `mcp.consent.loading` | Hold the GET. | Centered `svg.spin` under the "Whisperer · MCP" brand row (`span.tag-k` "Whisperer") | `GET /v1/mcp/oauth/authorize?<params>` → `McpConsent` (`mcp/contracts/consent.ts:7`) |
| `mcp.consent.error` | GET fails (4xx/5xx/401). | "Не удалось загрузить запрос" / "Ссылка авторизации недействительна или устарела. Повторите из приложения." | same |
| `mcp.consent.ready` | GET returns `{clientId,clientName:"Claude",redirectUri,scopes:["whisperer:meetings.read","whisperer:tracker.write"],resource,state,previouslyApproved}`. | Title "Разрешить доступ". Subtitle "Приложение «Claude» запрашивает доступ к вашим данным Whisperer.". "Запрашиваемые права" rows, domain plus action: "Встречи · чтение", "Трекер · запись" (`McpConsentPage.tsx:105-129`). "После подтверждения вы вернётесь на <redirectUri>". Buttons "Разрешить" / "Отклонить". | – |
| `mcp.consent.working` | Click "Разрешить" and hold the POST. | "Разрешить" button shows a spinner. On success, hard redirect to `redirectUri?code=…&state=…`. | `POST /v1/mcp/oauth/authorize` (form-urlencoded) → `{code,state,redirectUri}` (`api/oauth.ts:20-34`) |
| (deny) | Click "Отклонить". | External redirect to `redirectUri?error=access_denied&state=…` | – |

---

## `/prompts`: prompt library

Access `auth`, inside the shell. Nav item "Промпты" (audience user). Free, paid and admin can all open it; no paywall.
- Admin: `GET /admin/prompts` returns platform-global rows for admins (`platform-admin/api/platformPrompts.ts:12-18`).
- Free: skills install calls return 403 `subscription_required`.

Nav-hover prefetch: `GET /v1/admin/prompts` (`prompts/feature.ts:44-50`).

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `prompts.list.loading` | Hold `/admin/prompts`. | `Card` with `svg.spin` under the KPI strip; KPIs show "—" (`PromptsPage.tsx:216-221`) | `GET /v1/admin/prompts` → `PromptOut[]` (`prompts/contracts/types.ts:36`); `GET /v1/admin/prompts/stats` → `PromptStats` (`:25`) |
| `prompts.list.empty` | `[]`, any error, or a filter or search with no match. | EmptyState "Промптов нет" / "Создайте первый — например, «Ассистент собеседования» с ролью «Ответы в эфире»." with button "Создать" (`:222-232`) | same |
| `prompts.list.populated` | Several prompts. | PageHeader h1 "Промпты", eyebrow "Студия". KPI tiles "Всего" (subtext "из них активных: N"), "Вызовов", "Средняя задержка", "Расход сегодня" (`:326-388`). Table headers "№, Название, Роль, Метки, Версия, Обновлён". Rows show an 8-char id, a role Tag, `#tags` or "—". | – |
| `prompts.list.row-hover` | Hover a row. | Row turns `bg-primary` (state set via mouseenter) (`:390-461`) | – |
| `prompts.list.filter.<role>` | Click role tabs "Все", "Ответы в эфире", "Скриншоты", "Код", "System Design", "Заметки и карты" (`:32-35`; `contracts/roles.ts`). | Active tab is `bg-foreground`. Rows are filtered client-side. | – |
| `prompts.list.role-tooltip` | Hover or focus a role tab. | `[role=tooltip]` portal with help text, e.g. "Все промпты аккаунта — любой роли." (`:276-324`) | – |
| `prompts.kpi.empty-runs` | stats `runs_30d:0`. | Subtext "появится после первого вызова" | – |
| `prompts.delete-confirm` | Click row trash `button[title="Удалить промпт"]`. | `dialog[aria-label="Удалить промпт"]`, message "Удалить промпт «X»? Это действие необратимо.", buttons "Отмена" / "Удалить" (`:260-271`) | `DELETE /v1/admin/prompts/{id}` |
| `prompts.create` | Click "Новый промпт" (`[data-onboarding="prompts-create"]`). | Navigates to `/prompts/{newId}` | `POST /v1/admin/prompts` → `PromptOut`; `POST /v1/me/onboarding/progress` `{done_action:"first_prompt"}` |
| `prompts.import.*` | Set a file on `input[aria-label="Импорт"]` (hidden). | Toasts "Импортировано: N", "Пропущено: N", "В файле не нашлось промптов", "Не удалось прочитать файл — ожидается JSON" (`:58-84`) | `POST /v1/admin/prompts`, sequentially per prompt |
| `prompts.skills.hub-idle` | Click "Скиллы" (`[data-onboarding="prompts-skills"]`). | `dialog[aria-label="Скиллы"]` (720 px). Toggles "Готовые" (pressed), "Свой репозиторий", "Мои (N)". Search input, EmptyState "Каталог готовых скиллов" (`SkillLibraryModal.tsx:20-72`; `SkillHubTab.tsx:18-107`) | `GET /v1/me/skills` → `SkillOut[]` (`leo/contracts/skillTypes.ts:3`) |
| `prompts.skills.hub-searching` / `.hub-results` / `.hub-nothing` | Type at least 2 chars, e.g. "review". | "Ищу…" with spinner / rows: mono slug, "{repo} · установок: N", button "Установить" or a disabled "Установлен" / EmptyState "Ничего не нашлось". Note: a search error also shows "Ничего не нашлось". | `GET /v1/me/skills/search?q=` → `SkillHubHit[]` (`skillTypes.ts:17`) |
| `prompts.skills.install-error` | Install returns 403 `{"detail":"subscription_required"}` (Free), or another code. | `div[role=alert]` red, e.g. "Скиллы доступны на платном тарифе" (code→text map `hooks/useSkills.ts:17-42`) | `POST /v1/me/skills` `{repo,slug,source}` → `SkillOut` |
| `prompts.skills.repo-*` | Toggle "Свой репозиторий"; type `owner/repo`; click "Найти скиллы". | Idle EmptyState "Свой скилл из GitHub". Loading button. Results rows with path or "корень репозитория". Error alert, e.g. "Репозиторий не найден или он приватный" (`SkillRepoTab.tsx`) | `GET /v1/me/skills/discover?repo=` → `SkillDiscovery` (`skillTypes.ts:31`) |
| `prompts.skills.mine-empty` / `.mine-populated` | Toggle "Мои (N)". | "Пока ни одного скилла" / rows with `{repo}/{path} · {ref7}`, description, IconButtons "Обновить из репозитория" (`.spin` while pending) and "Удалить из библиотеки" (`SkillMineTab.tsx`) | `POST /v1/me/skills/{id}/refresh` (toast "Скилл обновлён из репозитория"); `DELETE /v1/me/skills/{id}` |

**Hazards:** `.rise` animations, row hover state, dates via `toLocaleDateString` (browser TZ), locale numbers, `formatSpend` currency, `.pop` on dialogs, `useDeferredValue` search.

---

## `/prompts/:id`: prompt editor

Access `auth`, inside the shell. Example `/prompts/7c9e6679-7425-40de-944b-e07fc1f90ae7`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `prompts.editor.loading` / `.error` | Hold, or return 404 for `GET /admin/prompts/{id}`. | **Blank content area**: the page returns `null` (`PromptEditorPage.tsx:36`). No error UI. | `GET /v1/admin/prompts/{id}` → `PromptOut` |
| `prompts.editor.populated` | Prompt OK. | Back link "Все промпты"; eyebrow "Промпт · {Ответы в эфире}" or "Промпт · без роли"; h1 name or "Без названия"; "Переменных: N · версия v1". Cards "Редактор" (inputs "Название", "Версия", select "Роль" with "?" HelpTip, "Метки (через запятую)", textareas "Системный промпт", "Пример запроса для теста") and "Тестовый прогон" (`:144-238`). | – |
| `prompts.editor.role-help` | Role selected. | Help paragraph under the select, e.g. "Основные ответы ассистента: …" (`:188-192`) | – |
| `prompts.editor.variables` | System or template text contains `{{client}}`. | "Переменные" block with code `{{client}}` and an input (`:351-369`) | – |
| `prompts.editor.autosave` / `.save-error` | Edit any field; saves after 700 ms idle (`shared/hooks/useAutosave.ts:7`). | No visual cue on success. Toast "Не удалось сохранить изменения" on error. | `PATCH /v1/admin/prompts/{id}` (`PromptInput`, `types.ts:11`) |
| `prompts.testrun.idle` | Default. | Placeholder "Ответ появится здесь и будет печататься постепенно, как живой.", button "Прогнать" | – |
| `prompts.testrun.streaming` | Click "Прогнать"; stream chunks. | Button "Стримим…" (disabled, spinner); output text followed by `span.cursor` (blinking ▮) (`:371-395`) | `POST /v1/admin/prompts/{id}/test` (SSE, JSON `{variables,role,system_prompt,user_prompt_template}`) |
| `prompts.testrun.done` | Final `data: [DONE]`. | Output only. **Without `[DONE]` the button stays "Стримим…" forever.** | same |
| `prompts.testrun.error` | HTTP 403 / 404 / other, or an in-stream `data: {"error":"…"}`. | `div[role=alert]` red: "Нет доступа к этому промпту." / "Промпт не найден." / `detail` / "Не удалось выполнить прогон. Попробуйте ещё раз." (`:265-269,314-317`) | same |
| `prompts.editor.skills-empty` | `skills:[]`. | Skills card with dark header "Скиллы", HelpTip, button "Подключить", text "Скиллы не подключены — промпт работает как есть." (`leo/ui/skills/PromptSkillsCard.tsx`) | – |
| `prompts.editor.skills-populated` | `skills:[{skill_id,slug,description,mode}]` (`PromptSkillRef`, `leo/contracts/types.ts:4`). | Rows with mono slug, toggle "Дополняет" / "Заменяет", trash `[aria-label="Отключить от промпта"]`. With any `replace`: note "Скилл в режиме «Заменяет» вытесняет текст системного промпта — в модель уйдёт он." | `PUT /v1/admin/prompts/{id}/skills` `{items:[{skill_id,mode}]}` → `PromptOut` |
| `prompts.editor.skills-full` | 3 skills attached. | "Больше трёх скиллов на один промпт подключить нельзя."; "Подключить" disabled | – |
| `prompts.editor.skills-error` | PUT returns an error. | `div[role=alert]` with the mapped text | – |
| `prompts.editor.skill-picker` | Click "Подключить". | `dialog[aria-label="Скиллы"]`, opening on "Мои (N)" when N>0. Rows have "Подключить" or Tag "Подключён" (`SkillLibraryModal.tsx:39`) | `GET /v1/me/skills` and the other skills endpoints |

**SSE format for the test run:** no event names. Frames are `data: {"choices":[{"delta":{"content":"…"}}]}`, `data: {"error":"…"}`, and `data: [DONE]`. Non-JSON frames are ignored (`PromptEditorPage.tsx:303-323`). It uses the store token without `ensureAccessToken`.

**Hazards:** `.cursor` blink (1 s steps), autosave timer, HelpTip hover, `.rise`.

---

## `/models`: model assignments and catalog

Access `auth`, inside the shell. Nav "Модели". **No paywall**: free users see only `allowed!==false` models in the role selects; the catalog lists everything. Admins can also open it.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `models.loading` | Hold either request. **Also shown forever on error.** | Only `div.p-20 svg.spin`, no header (`ModelsPage.tsx:48-54`) | `GET /v1/me/models/configs` → `CatalogModelOut[]` (`models/contracts/types.ts:61`); `GET /v1/me/models/roles` → `RoleAssignmentOut[]` (`:99`) |
| `models.populated` | Both OK. | h1 "Модели", eyebrow "Цех". Section "Назначения по ролям" with six rows "Ответы в эфире", "Скриншоты", "Код", "System Design", "Заметки и карты", "Стенограмма" (no Leo row). Section "Каталог" table with headers "№, Провайдер · модель, Способности, Группа" (`:56-126`). | – |
| `models.role.select-open` | Click a role combobox. | Radix listbox with eligible models of the right `type`. The vision row lists only vision-capable models (`:149-155`; `model/scorecard.ts:114-122`). | – |
| `models.role.blind-vision` | Vision assignment points at a non-vision model. | Select shows placeholder "Выбрать…" (`:160-165`) | – |
| `models.role.reasoning.*` | `reasoning_control` is `optional` / `always` / `none`; `reasoning_default:null` with no choice. | Switch `[aria-label="Рассуждать по шагам в роли «…»"]` plus "авто" / "всегда включено" / "не поддерживается" (`:269-298`) | – |
| `models.role.temp-unsupported` | `supports_temperature:false`. | "не поддерживается" in place of the slider | – |
| `models.role.saving` / `.saved` | Change model, temperature (range `[aria-label="Температура"]`) or max tokens; saves after 600 ms debounce. | "Сохр…", then "✓" (`:299-301`) | `PUT /v1/me/models/roles/{role}` `{model_id,temperature,max_tokens,reasoning}` |
| `models.catalog.row-expanded` | Click a row or `button[aria-label="Описание модели {display}"]`. Only rows with `blurb` or `ratings` expand. | `[aria-expanded=true]`; blurb paragraph. When `ratings` exist: six star rows ("Интеллект", "Код", "Агентность", "Контекст", "Скорость", "Выгода"), a radar SVG, and the source line "Цена и контекст — наши данные, …" (`:358-415`; `ui/ModelScorecard.tsx:84-106`) | – |
| `models.mobile` | Viewport ≤860px. | Catalog renders as stacked cards (`ConfigCard`); whole-card toggle button (`:420-477`) | – |

**Hazards:** Radix portal, autosave debounce, chevron `rotate-180` transition, range slider, `ProviderMark` (data-URI logos only, no network).

---

## `/admin/ai-models`: admin model registry

Access `admin`, inside the shell. Non-admins are redirected to `/analytics`. Nav "AI-модели". All UI strings are hard-coded Russian (no i18n).

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `admin-models.populated` | All OK. | h1 "Модели и расходы (OpenRouter)"; sections "01 Баланс OpenRouter", "02 Расходы по моделям", "03 Реестр моделей (импорт из OpenRouter)", "04 Каталог моделей", "05 Дефолты моделей" (`AiModelsPage.tsx:84-127`) | – |
| `admin-models.balance.loading` / `.error` / `.ok` | Hold, fail or succeed. | spinner / "Баланс OpenRouter недоступен." / cards "Баланс (остаток)", "Пополнено", "Израсходовано" in USD (`:24-47`) | `GET /v1/admin/models/balance` → `OpenRouterBalance` (`types.ts:84`) |
| `admin-models.usage.empty` / `.populated` | `[]` or rows. | "Расходов по моделям пока нет." / table with headers "Модель, Вход (ток.), Выход (ток.), USD, RUB" (`:49-82`) | `GET /v1/admin/models/usage` → `ModelUsageRow[]` (`types.ts:91`) |
| `admin-models.import.idle` | Default. | Input "Тикер модели (provider/model)" (placeholder `anthropic/claude-haiku-4.5`), button "Получить спеки" (`ModelRegistrySection.tsx:53-168`) | – |
| `admin-models.import.preview` | Enter a ticker; click "Получить спеки". | Display name, Tags (id, "N ctx", capabilities), selects "Группа (тир)" and "Тип", inputs "Цена вход (USD/1k)" and "Цена выход (USD/1k)", button "Добавить в реестр" | `GET /v1/admin/models/registry/preview?ticker=` → `RegistryPreview` (`types.ts:1`) |
| `admin-models.import.price-unknown` | Preview with `price_known:false`. | Red Tag "цена не задана — введите вручную"; price fields empty; import disabled | – |
| `admin-models.import.error` | Preview fails. | "Не удалось получить спеки: проверьте тикер и доступность OpenRouter." | – |
| `admin-models.registry.empty` / `.populated` | `[]` or rows. | "Реестр пуст — импортируйте модель выше." / table with headers "Модель, Тип, Тир, Версия, Цена вх., Цена вых., USD, Вкл." (`:279-313`) | `GET /v1/admin/models/registry` → `RegistryModel[]` (`types.ts:15`); `POST /v1/admin/models/registry` (`RegistryImport`, `types.ts:34`) |
| `admin-models.registry.dirty-price` | Edit a price input (`[aria-label="Цена вход …"]`). | Button "Сохранить цену" | `PATCH /v1/admin/models/registry/{id}` |
| `admin-models.registry.delete-confirm` | Click "Удалить" (`[aria-label="Удалить … из реестра"]`). | `dialog[aria-label="Удалить модель"]` "Удалить модель X из реестра? Историческая статистика расходов сохранится." | `DELETE /v1/admin/models/registry/{id}` |
| `admin-models.catalog` | Default. | Table with headers "№, Модель, Провайдер, Тип, Группа, Источник, Вкл.". Tags "реестр" / "встроенная"; text "в коде" (`CatalogTable.tsx:33-132`) | `GET /v1/me/models/configs` (query key `admin-model-catalog`) |
| `admin-models.defaults` / `.error` / `.saving` | Default; then click "Сохранить дефолты". | Matrix with headers "Тариф × Ответы / Код / Зрение / System Design / Генерация / Транскрипция", selects `[aria-label="Модель для Free · Ответы"]`, stale options "(вне каталога)" / "(без зрения)", card "Модель агента Леo" select. Errors such as "Заполните все ячейки матрицы." or "На роль «Зрение» нужна модель…". Button text "Сохранение…" while saving (`ModelDefaults.tsx:140-243`). | `GET`/`PUT /v1/admin/models/model-defaults` (`ModelDefaultsOut` `types.ts:116`, `ModelDefaultsIn` `:123`) |

**Hazards:** `.rise`, sticky matrix column with horizontal scroll, Radix portals, locale formatting via `toLocaleString("ru-RU")`.

---

## `/hub`: hub list

Access `auth`, inside the shell. Nav "Хаб" with tag "Beta". **No client paywall**: any `GET /hubs` error renders the empty state.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `hub.list.loading` | Hold `/hubs`. | `div.py-16 svg.spin` (`HubPage.tsx:103-106`) | `GET /v1/hubs?include_archived=false` → `{items:HubOut[]}` (`hub/api/hubApi.ts:20-53`; domain `Hub` at `hub/contracts/types.ts:6`); `GET /v1/me/tracker/projects?archived=false` → `TrackerProject[]` (`tracker/contracts/types.ts:6`) |
| `hub.list.empty` | `{items:[]}` or an error. | EmptyState "Хабов пока нет" / "Создайте первый — и встречи начнут попадать в него сами…" with button "Создать хаб" (`:107-117`) | same |
| `hub.list.populated` | Items, e.g. one with `overdue:2`, one with `tracker_project_id:null`, one archived. | h2 "Хабы · N"; grid of `.hub-card` sorted overdue desc, then no-board first (`:57-60`). Each card: Link name, Tag "просрочено: 2", board line "работа уходит в «Доска»" or red "доска не выбрана — работе некуда идти", button "Открыть" (`HubCard.tsx:103-167`). | – |
| `hub.list.no-boards` | Tracker projects `[]`. | Red paragraph "В трекере нет ни одной доски — создайте её, иначе хабу некуда отправлять работу." (`:80-87`) | – |
| `hub.list.all` | Click toggle "Все" (`aria-pressed`). | Archived cards at opacity-60 with Tag "в архиве" | `GET /v1/hubs?include_archived=true` |
| `hub.card.menu` | Click `button[aria-label="Действия"]` on a card, or right-click the card. | `div.pop.fixed` menu: board names (check icon on the current one), "Доска не выбрана" (only when a board is set), "Переименовать", "В архив" / "Вернуть", "Удалить" (red) (`HubCard.tsx:57-97,169-171`) | Board pick: `PUT /v1/hubs/{id}/target` `{tracker_project_id}`; "Вернуть": `PUT /v1/hubs/{id}/archived` `{archived:false}` |
| `hub.card.rename` | Menu → "Переименовать". | `dialog[aria-label="Переименовать"]` with input `[aria-label="Название хаба"]` (prefilled), buttons "Отмена" / "Переименовать" | `PATCH /v1/hubs/{id}` `{name}` |
| `hub.card.delete-confirm` | Menu → "Удалить". | `dialog[aria-label="Удалить «X»?"]` "Хаб исчезнет вместе с адресацией. Встречи, задачи и документы останутся на месте." with buttons "Отмена" / "Удалить" | `DELETE /v1/hubs/{id}` |
| `hub.closing.loading` / `.clear` / `.left` | Menu → "В архив" on a live hub. | `dialog[aria-label="Убрать «X» в архив?"]` containing a spinner / "В деле ничего не осталось — можно убирать." (dark confirm) / "В деле осталось незакрытым: N" plus up to 5 loop lines (danger confirm). Button "Убрать в архив" (`HubClosingGate.tsx:22-71`). | `GET /v1/hubs/{id}/pulse` → `{items:LoopOut[]}` (`hubApi.ts:102-120`); `PUT /v1/hubs/{id}/archived` `{archived:true}` |
| `hub.create.modal` | Click "Создать хаб". | `dialog[aria-modal][aria-label="Новый хаб"]` with input "Название хаба" (**autoFocus**), placeholder "Например: Альфа Бета Гамма", hint "Клиент, проект, направление — как называете это вы.", buttons "Отмена" / "Создать хаб" (disabled when empty) (`HubCreate.tsx:25-85`) | – |
| `hub.create.error` | POST returns 4xx `{"detail":"name_taken"}`. | Input error text "Хаб с таким названием уже есть". Other codes: `name_too_short`/`name_required` → "Слишком короткое название", `name_too_long`, `too_many_hubs`, fallback "Не удалось сохранить" (`HubPage.tsx:28-33,159`) | `POST /v1/hubs` `{name,kind:"client",tracker_project_id:null}` → `HubOut` |

**Hazards:** `.hub-card:hover` translate plus hard shadow (`hub/styles.css`), `.rise`/`.pop`, autoFocus caret, context-menu position taken from click coordinates (closes on scroll or resize).

---

## `/hub/:hubId`: hub detail

Access `auth`, inside the shell. Example `/hub/3fa85f64-5717-4562-b3fc-2c963f66afa6`. With a UUID path, the Leo widget shows `leo.panel.hub-scope`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| `hub.detail.loading` | Hold `GET /hubs/{id}`. | `svg.spin` (`HubDetailPage.tsx:44-50`) | `GET /v1/hubs/{id}` → `HubOut`; `GET /v1/hubs/{id}/feed` → `{entries:FeedEntryOut[],facts_total}` (`hubApi.ts:208-245`); `GET /v1/me/tracker/projects?archived=false` |
| `hub.detail.gone` | 404, any error, or a non-UUID id. | EmptyState "Хаб не найден" / "Возможно, он в архиве или удалён." (`:51-59`) | – |
| `hub.detail.populated` | Hub OK. | Link "Все хабы"; h1 name; stats "встреч" / "договорённостей"; board line; cards "Цель", "Что горит", "Материалы"; feed card "Что здесь происходило" (`:65-168`) | plus `GET /v1/hubs/{id}/pulse`; `GET /v1/hubs/{id}/materials` |
| `hub.detail.feed.loading` / `.empty` / `.populated` | Feed hold / `entries:[]` / entries with facts. | spinner / "Пока ни одной встречи" + "Встречи попадут сюда сами…" / `ol` timeline: title (or "Встреча без названия"), mono datetime, fact kind labels "Решение", "Обещание", "Риск", "Проблема", "Открытый вопрос", badge "вытеснено" (opacity-60), "Ничего, что стоило бы запомнить" for empty facts (`HubFeedList.tsx:36-110`) | – |
| `hub.detail.digest` | Feed has entries and the digest has a non-empty list. | Section "После последней встречи" with groups "Не обсуждали" (+ "держит дело, а на встрече о нём не сказали ни слова"), "Появилось", "Закрылось" (opacity-60). Hidden when all lists are empty (`HubDigest.tsx:22-54`). | `GET /v1/hubs/{id}/digest/{entries[0].meeting_id}` → `{opened,closed,untouched:LoopOut[]}` (`hubApi.ts:138-152`; `HubDigest` type `types.ts:131`) |
| `hub.detail.charter.empty` / `.filled` / `.editing` | `purpose`/`success` null / set / click edit. | Button "Добавить: зачем это дело и что считается успехом" / purpose paragraph plus "Успех: …" plus "изменить" (**`.quiet-reveal`: opacity 0 except on hover on hover-capable devices**) / inputs "Зачем это дело" and "Что считается успехом" with buttons "Сохранить" / "Отмена" (`HubCharter.tsx:50-160`) | `PUT /v1/hubs/{id}/charter` `{purpose,success}` |
| `hub.detail.loops.loading` / `.clear` / `.populated` | Pulse hold / `[]` / items. | spinner / "Ничего не висит — всё закрыто" / `li` LoopLines: icon, text, suffix like "просрочено на 4 дн." (red for overdue and contradiction), second line detail / "круг 3" / "вы отклоняли это раньше", dismiss `[aria-label="Это не так"]` (`.quiet-reveal`, only when `fact_id` is set) (`HubLoops.tsx`; `LoopLine.tsx`) | `POST /v1/hubs/{id}/pulse/dismiss` `{fact_id,kind}` |
| `hub.detail.materials.loading` / `.empty` / `.populated` | Materials hold / `{items:[]}` / items. | spinner / "Пока ничего — сохранённые итоги встреч появятся здесь." / links (`href="/app/knowledge-base?doc=…"` or `/app/storage?file=…`) with datetime and detach `[aria-label="Убрать из хаба"]`; button "Добавить материал" (`HubMaterials.tsx:45-129`) | `GET /v1/hubs/{id}/materials` → `{items:[{id,kind,ref_id,title,session_id,created_at}]}` (`hubApi.ts:254-268`); `DELETE /v1/hubs/{id}/materials/{mid}` |
| `hub.detail.material-picker` / `.results` / `.nothing` / `.upload-error` | Click "Добавить материал"; type a query (200 ms debounce). | `dialog[aria-label="Добавить материал"]` with input "Найти документ или файл" (**autoFocus**), result buttons / "Ничего не нашлось", button "Загрузить файл", alert "Не удалось загрузить файл" (`:138-218`) | `GET /v1/me/search?q=&per_domain=5&domains=documents,files` (`hubApi.ts:296-311`); `POST /v1/hubs/{id}/materials` `{kind,ref_id,title}`; `POST /v1/me/storage/upload` (multipart) → `{id,name}` |

Wire shapes in `hubApi.ts`: `HubOut` :20, `LoopOut` :102, `FeedFactOut` :208, `FeedEntryOut` :217. Domain types in `types.ts`: `Loop` :45, `FeedEntry` :79, `HubMaterial` :103.

**Hazards:**
- `formatDateTime` uses the browser default TZ (`shared/lib/format.ts:95-98`).
- `.quiet-reveal` hover-only elements.
- Sticky summary column (`lg:sticky`).
- autoFocus in the picker; debounce.

---

## Hub chip on the meeting page (hub feature, hosted on `/meetings/:id`)
`MeetingHub` is rendered by meetings' `MeetingChipRow` for non-ephemeral meetings (`meetings/ui/detail/MeetingChipRow.tsx:86`; `hub/ui/MeetingHub.tsx:62-230`).

States:
- Hidden while loading.
- Icon-only chip (`aria-label="Отнести к хабу"`).
- Hint dot plus aria-label "Похоже на".
- Labelled chip with the hub name; the icon turns red when the hub has no board.
- Popover menu `dialog[aria-label="Отнести к хабу"]` with: "у хаба нет доски", "Похоже на {name}" plus reason (e.g. "встречи этой серии уже здесь"), "Создать первый" (navigates to `/hub`), other hubs, "Открыть дело", "снять".

Endpoints:
- `GET /v1/hubs/of-meeting/{sessionId}` → `HubOut|null`
- `GET /v1/me/sessions/{id}/hub-suggestion` → `{hub_id,signal,confidence}|null` (`hubApi.ts:168-190`)
- `GET /v1/hubs`
- `POST /v1/hubs/{hubId}/meetings` `{session_id,primary:true}`
- `DELETE /v1/hubs/{hubId}/meetings/{sessionId}`

---

## Redirect-only and gate redirects
- `/settings/mcp` → `/cabinet/mcp` with the query string preserved (`mcp/feature.ts:28`).
- `/cabinet/leo` and `/cabinet/mcp` for a free user → `/cabinet`; for an admin → `/dashboard` (`CabinetModal.tsx:91-93`; `guards.tsx:33-37`).
- `/admin/ai-models` for a non-admin → `/analytics` (`guards.tsx:26-30`).
- Any inside-shell route without a session → `/login`. There is no return-to (`guards.tsx:19-24`).
- prompts, models and hub declare no redirect routes.

---

## Cross-cutting notes
- **Auth bootstrap:** localStorage `wh-auth` persists only `{state:{csrfToken,user}}` (`shared/auth/authStore.ts:27-28`). The access token lives in memory. `BootGate` calls `POST /v1/auth/refresh` (cookie plus `X-CSRF-Token`) and then `GET /v1/auth/me` (`app/providers/BootGate.tsx`). Mock both. `user.id` must match between `wh-auth` and `/auth/me` so the Leo widget is not remounted and the Leo localStorage keys line up.
- **Retry policy:** queries retry once on 5xx/network errors and never on 4xx except 408/429 (`shared/query/queryClient.ts`). Error states settle after about one retry delay.
- **Error branches are mostly invisible:**
  - Infinite spinner: `/models`, MCP server tab, Leo cabinet blocks.
  - Empty state: `/prompts`, `/hub`, MCP clients.
  - Blank page: `/prompts/:id`.
  - Dedicated error UI only on `/connect/mcp`, `/hub/:id` ("Хаб не найден"), and the admin balance card.
- **Animations not covered by reduced motion:** `.rise` 360 ms, `.pop` 180 ms, `.pulse-y` 1.8 s infinite, `.spin`, `.cursor` blink (`shared/styles/globals.css:496-546`). Inject `*{animation:none!important;transition:none!important}`. Emulating `prefers-reduced-motion: reduce` additionally disables LeoFace gaze and blink, ledger animations and wave bars.
- **Leo launcher on every shell page:** fixed bottom-right with pointer-tracking eyes. Mask it or move the pointer to a fixed position before each shot.
- **Onboarding tour:** may auto-start on any page from `GET /v1/me/onboarding` (`onboarding/hooks/useTourRunner.ts:75-95`). Return a finished or skipped status. Anchors `[data-onboarding=…]` exist on the agent FAB, `prompts-create`, `prompts-skills`, `page-header` and `cabinet-tab-leo|mcp`.
- **Time and locale:** freeze `Date.now`, TZ and `navigator.language`. Affected: ledger elapsed times, "Обновлено …", errand and memory dates, hub datetimes, prompt dates, KPI formats.
- **WebSockets:** `/v1/ws/user` opens on every shell page and reconnects with backoff, so stub it or accept failures. `/v1/ws/voice` opens only in voice mode. Both authenticate with subprotocols `["whisperer-bearer", token]`.
- **SSE replay rules:**
  - Leo: named events, `event: done` with `data: {}` required to end a turn, `action_result` required to settle a confirm.
  - Prompt test: unnamed `data:` frames with OpenAI-style chunks, `[DONE]` required.
- **External resources:**
  - YouTube thumbnails and iframes inside chat answers.
  - Connector popups and OAuth redirects (`window.open`, `window.location.assign/href`).
  - Fonts are served from `/fonts/` (backend in dev, via the vite proxy at `vite.config.ts:147-160`).
- **Cabinet host:** `/cabinet/*` polls `GET /v1/me` every 15 s, also calls `GET /v1/me/referral`, and on direct URL renders `AnalyticsPage` underneath (its endpoints are owned by the analytics feature).