> Draft commit `589917e847f7d7213b3af5a3959bcc88c7500fe7`, read on 2026-10-01. File paths and line numbers refer to `/root/whisperer/frontend` at that commit.

# UI-state inventory: meetings, calendar, context, knowledge, search

All paths are relative to the router basename `/app` (`src/app/main.tsx:48`), so the full URL is `/app<path>`.

## Conventions (read first)

**Auth gate.** Inside-shell routes pass `RequireAuth` when either an access token is in memory or a `user` is persisted (`src/app/router/guards.tsx:19-24`).
- localStorage `wh-auth` persists only `{csrfToken, user}` (`src/shared/auth/authStore.ts:27-28`). The access token is never persisted.
- First API calls go out without a token. The 401 interceptor then calls `POST /v1/auth/refresh`, which returns `LoginResponse {access_token, csrf_token}` (`src/shared/api/client.ts` `postRefresh`).
- SSE calls `ensureAccessToken()` first, which does the same refresh.
- Harness should mock `POST /v1/auth/refresh`, or answer 200 regardless of the auth header.

**Paid vs free.** `isPaidActive(user)` is in `src/shared/entitlements/subscription.ts:9-15`. A user is paid when all of these hold:
- `subscription.status === "active"`
- `subscription.tariff.code !== "free"`
- `expires_at` is null or in the future. This compares against `Date.now()`, so it is a time hazard.

**Paywall UI.** `PremiumLocked` (`src/shared/entitlements/PremiumBanner.tsx:61-83`) renders a PageHeader `h1` plus a banner:
- Title "Нужна подписка".
- Text "«{feature}» доступна только на платной подписке (Start, Pro или Max). Оформите подписку, чтобы открыть раздел."
- Button "Перейти к тарифам".

**Locale.** Set localStorage `wh.lang="ru"` (`src/shared/i18n/localeStore.ts:14`), or `user.language:"ru"` (it wins on sync, `src/shared/i18n/index.ts:112`).
- Feature strings live in `src/features/<name>/locales/ru.json`, not in `src/locales`.
- Common strings (`actions.*`, `premium.*`, `palette.*`, `search.*`, `uploads.*`) live in `src/locales/ru/common.json`.

**Retry policy** (`src/shared/query/queryClient.ts`):
- 4xx is not retried, except 408 and 429. Use 404/400 to get an error state immediately.
- 5xx is retried once, so the error UI shows after about 1 s.
- `staleTime` is 30 s. `refetchOnWindowFocus` is false.

**Shared primitive markers:**
- Spinner: `svg.spin` (`shared/ui/Spinner.tsx`).
- `ConfirmModal`: a non-modal `<dialog open aria-label="<title>">` (Popover).
- `Modal`: `<dialog aria-modal="true" aria-label="<title>">` with an `h2` title.
- `ContextMenu`: a portal `div.pop.fixed` of plain buttons, with no role.
- `Switch`: `[role=switch][aria-label]`.
- `Tabs` and `SegmentedToggle`: buttons with `aria-pressed`.
- Toasts: `[role=alert]` for errors, `[role=status]` otherwise.

---

## /meetings

- **Route:** `/meetings` → `LibraryPage`, access `auth` (`features/meetings/feature.ts:87`). Inside the shell, nested in the pathless layout `MeetingsLayout` (`feature.ts:84-96`).
- **Layout** (`pages/MeetingsLayout.tsx:17-31`):
  - Wrapper `div.mtg[data-skin="airy"]`.
  - Subnav `nav[data-onboarding="meetings-nav"]` with tabs "Библиотека" (`a.active` here), "Шаблоны", "Интеграции".
  - Local Suspense spinner while the child chunk loads.
- **Who sees it:** free and paid users see everything; there is no paywall. The nav item has `audience:"user"`, so it is hidden from admins, but the route is still open to them.
- **Server-gated actions:** "Сохранить в файлы" needs Pro/Max storage, otherwise you get an error toast. Import can be refused with 402 (minutes quota).

| state id | how to reach (URL + data + interaction) | marker | endpoints |
|---|---|---|---|
| meetings.layout.chunk-loading | First visit, lazy chunk not loaded | `.mtg svg.spin` inside `div.p-[60px]`, no `a.mtg-card-brand` | — |
| meetings.library.loading | `/app/meetings`; hold `GET /v1/me/sessions` | `svg.spin` in `div.p-15`. Aside shows "Встреч: 0"; the import panel is visible | GET /v1/me/sessions |
| meetings.library.error | `GET /v1/me/sessions` → 404 | Title "Не удалось загрузить встречи" + underlined button "Повторить" | same |
| meetings.library.empty | `GET /v1/me/sessions` → `[]` | "Встреч пока нет" + "Загрузите запись — расшифруем её, разделим говорящих и соберём заметки." | same |
| meetings.library.populated | Rows with `started_at` spread over today / yesterday / ≤6 days / older | Group headers `.mtg-eyebrow` "Сегодня" / "Вчера" / "На этой неделе" / "Ранее"; cards `a.mtg-card-brand[href="/app/meetings/<id>"]`; "Встреч: N" | same + GET /v1/me/folders |
| meetings.library.card-variants | Row `status` "processing" (yellow dot), "failed"/"error" or "recording"/"active" (red dot); `hub_name` set (hub line with grid icon); empty title (falls back to "Встреча") | Dot colour in `span.rounded-full` inline style; hub name text | same |
| meetings.library.folders-empty | `GET /v1/me/folders` → `[]` | "Создайте папку или перетащите сюда встречу." | GET /v1/me/folders |
| meetings.library.folders-populated | Folders with `parent_id` nesting | Button "Все встречи" (yellow when active), eyebrow "Папки", `button[aria-label="Создать папку"]`, rows with `button[aria-label="Меню папки"]` | same |
| meetings.library.folders-favorites | A folder with `favorite:true` | Eyebrow "Избранное" section; pin icon on the row | same |
| meetings.library.folder-expanded | Folder with children; click `button[aria-label="Развернуть"]` | Child rows indented; toggle now `aria-label="Свернуть"` | — |
| meetings.library.folder-selected | Click a folder row | Row has `bg-primary`; grid filtered by `folder_id` | — |
| meetings.library.folder-empty-selection | Click a folder that no meeting references | "В этой папке пусто. Перетащите сюда встречи из «Все встречи»." | — |
| meetings.library.folder-context-menu | Right-click a folder row, or click `button[aria-label="Меню папки"]` | Menu items "Создать папку", "В избранное" or "Убрать из избранного", "Переименовать", "Удалить папку" | — |
| meetings.library.folder-create-modal | Click `button[aria-label="Создать папку"]` | `dialog[aria-label="Создать папку"]`, eyebrow "Иконка и название", input placeholder "Название папки", 8-column icon grid, submit "Создать" | POST /v1/me/folders on submit |
| meetings.library.folder-rename-modal | Folder menu → "Переименовать" | `dialog[aria-label="Переименовать папку"]`, submit "Сохранить" | PATCH /v1/me/folders/{id} |
| meetings.library.folder-delete-confirm | Folder menu → "Удалить папку" | `dialog[aria-label="Удалить папку"]` with text "Удалить «X» и все вложенные папки? Встречи не удалятся." | DELETE /v1/me/folders/{id} |
| meetings.library.card-context-menu | Right-click a card | Items "Открыть", "Переименовать", "Сохранить в файлы", "Удалить". "Сохранить в файлы" is unique to this menu | — |
| meetings.library.card-rename-inline | Card menu → "Переименовать" | `a.mtg-card-brand input.mtg-card-rename[aria-label="Название встречи"]`, focused with text selected | PATCH /v1/me/sessions/{id} `{title}` on Enter/blur |
| meetings.library.delete-confirm | Card menu → "Удалить" | `dialog[aria-label="Удалить встречу"]` "Удалить встречу «X»? Действие необратимо." | DELETE /v1/me/sessions/{id} (optimistic) |
| meetings.library.toast-saved / -save-failed | Card menu → "Сохранить в файлы" | Toast "Сохранено в файлы: «name»" or "Не удалось сохранить в файлы" | POST /v1/me/sessions/{id}/save-to-storage `{format:"md",folder_id:null}` |
| meetings.library.toast-action-error | DELETE or PATCH fails | Toast "Не удалось выполнить действие со встречей — изменения отменены" | — |
| meetings.library.mobile-folders-collapsed / -expanded | Viewport ≤860px; click folders toggle | `button[aria-expanded]` "Папки" (or "Папки · выбрана" when a folder is selected) | — |
| meetings.library.import-idle | Default | `[data-onboarding="meetings-upload"]`, button "Загрузить запись", hint "Перетащите файл или нажмите · mp3, m4a, wav, mp4, webm и другие · до 25.0 МБ" | — |
| meetings.library.import-dragover | Drag a real OS file (DataTransfer types contains "Files") over the panel | Panel switches from `border-hairline` to `border-foreground bg-card` | — |
| meetings.library.import-refusal-client | `setInputFiles` on `input[aria-label="Файл записи"]` with `x.txt`, a 0-byte file, or a file >25 MB | Red line "Формат .txt не поддерживается — загрузите аудио или видео." / "Файл пустой или повреждён." / "Файл слишком большой — максимум 25.0 МБ." | — |
| meetings.library.import-refusal-server | POST import → 402 / 413 / 429 / 503, or detail `import_unavailable_no_logs` | "Исчерпан лимит минут тарифа." / "Слишком много запросов — попробуйте позже." / "Хранилище записей недоступно — попробуйте позже." / "Включён режим «без логов»: записи не сохраняются, поэтому импорт недоступен." | POST /v1/me/sessions/import |
| meetings.library.import-uploading | Valid .mp3; hold the POST | "Загрузка…" + stage "Загрузка" + 120px progress bar; upload button disabled | same |
| meetings.library.import-processing | POST → `{jobId}`; job GET → `{stage:"transcribing"}` or `{stage:"enhancing"}` | `job.fileName` + "Транскрипция" / "AI-заметки" + bar | GET /v1/me/sessions/import/{jobId} (polled every 3 s) |
| meetings.library.import-ready | Job `{stage:"ready"}` | "Готово" + button "Скрыть" | same |
| meetings.library.import-failed | Job `{stage:"failed", error:null}` | "Не удалось обработать файл" (or `job.error`) + "Скрыть" | same |

**Endpoints and response shapes**
- `GET /v1/me/sessions?q=&limit=100` returns `SessionRow[]` (`meetings/contracts/types.ts:251`). Called from `api/sessions.ts:7`, mapped by `rowToMeeting` in `api/apiProvider.ts`.
- `GET /v1/me/folders` returns `FolderDTO[]` (`api/orgApi.ts:6`, `:28`).
- `POST /v1/me/sessions/import` (multipart field `file`) returns `{jobId}` (`api/importApi.ts:16`).
- `GET /v1/me/sessions/import/{jobId}` returns `ImportJob` (`types.ts:227`), via `importApi.ts:29`.
- Mutations:
  - `DELETE /v1/me/sessions/{id}`
  - `PATCH /v1/me/sessions/{id}` with `{title}`
  - `POST /v1/me/sessions/{id}/save-to-storage` returns `{file_id,name,size}` (`sessions.ts:66`)
  - `POST /v1/me/folders`, `PATCH /v1/me/folders/{id}`, `POST /v1/me/folders/{id}/move`, `DELETE /v1/me/folders/{id}`
  - `PUT /v1/me/sessions/{id}/folder` with `{folder_id}` (drag-and-drop) — `orgApi.ts:28-66`

**Hazards**
- Group labels depend on `new Date()` and local timezone (`model/grouping.ts:15`).
- `formatDateTime` follows locale and timezone. `formatDuration` uses `hh:mm:ss`.
- Import job polls every 3 s. The progress bar has a 200 ms width transition.
- Folder modal: input focus after 10 ms (`CreateFolderModal.tsx:32`) plus `.pop` animation (180 ms).
- Card hover transform (`.mtg-card-brand`).
- Folder sort uses `localeCompare`.
- The list is capped at `limit:100`.

---

## /meetings/:id

- **Route:** `MeetingDetailPage`, access `auth` (`feature.ts:95`), inside the shell.
- **Doc mode** (`model/routes.ts`): the meetings subnav is hidden, and the AppShell sidebar defaults to the 66px rail (`app/shell/AppShell.tsx:65-75`).
- **Who sees it:** free and paid users.
- **Paid-only part:** the "Отправить" group in the "⋯" menu. For free users the integrations query is disabled (`hooks/useIntegrations.ts:93-106`).
- **Example URL:** `/app/meetings/m1`.
- **Default view:** "enhanced" if `note.enhancedMarkdown` is non-empty, otherwise "draft" (`MeetingDetailPage.tsx:43`).

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| meetings.detail.loading | Hold `/full` or `/note` | `svg.spin` in `div.p-[60px]`, no `.mtg-doc-bar` | GET /full, GET /note |
| meetings.detail.not-found | `GET /v1/me/sessions/m1/full` → 404, or `/note` → 404 | "Встреча не найдена" + link "← К списку" | same |
| meetings.detail.draft | `note.enhancedMarkdown: null`, `draftMarkdown: "text"` | `[aria-label="Заметки встречи"]` (CodeMirror `.mtg-canvas`) and `button[aria-label="Мой черновик"][aria-pressed="true"]` | PUT /v1/me/sessions/{id}/note/draft (autosave 700 ms after typing) |
| meetings.detail.draft-placeholder | `draftMarkdown: ""` | CodeMirror placeholder "Запишите тезисы по встрече — AI дополнит их в AI-версии…" | — |
| meetings.detail.draft-format-toolbar | Select text in the draft | `[role="toolbar"][aria-label="Форматирование"]` | — |
| meetings.detail.enhanced | `enhancedMarkdown: "# H1\n..."` | `[data-doc-prose] .mtg-prose`; chip `button.mtg-chip[title="AI-версия"][aria-expanded]` with chevron (menu trigger) | GET /v1/me/templates (EnhancedMenu mounts) |
| meetings.detail.enhanced-menu | From `enhanced`, click the "AI-версия" chip | `.mtg-menu` containing `button[aria-label="Пересобрать AI-версию"]`, label "Шаблоны", template rows, links "Все шаблоны…" and "Новый шаблон" (→ `/templates?new=1`) | same |
| meetings.detail.enhanced-empty | `enhancedMarkdown: null`; click `button[aria-label="AI-версия"]` | "Соберём структурированные заметки и майнд-карту из ваших тезисов и транскрипта." + button "Собрать AI-версию" | — |
| meetings.detail.enhanced-streaming | Click "Собрать AI-версию"; SSE stays open with `event:status data:{"phase":"generating"}`, then `event:delta data:{"text":"…"}` | `output.mtg-gen-card` "Собираем заметки…" (phase "saving" → "Сохраняем…", "mindmap" → "Собираем майнд-карту…"). The card shows from the click, before any event (checked in step 4 of D2) | SSE POST /v1/me/sessions/{id}/note/regenerate-enhanced/stream |
| meetings.detail.enhanced-error | SSE returns non-OK, or the connection drops, or `event:error {code, message}` | `p.mtg-doc-error`. With no content: "Не удалось собрать AI-версию." + button "Попробовать снова". `event:error` shows its `message` (the draft sends Russian text, `api/me_notes.py:339`). 402, 429 and a drop also show the generic text — a defect, see Findings | same |
| meetings.detail.enhanced-truncated | SSE `event:warning data:{}` | `p.mtg-doc-error` "Заметка упёрлась в лимит длины — список задач мог собраться не полностью." | same |
| meetings.detail.enhanced-private | `SessionFull.ephemeral: true`; click the AI chip | "Приватная встреча (no-logs) — AI-версия не создаётся." | — |
| meetings.detail.mindmap-loading | Click `button[aria-label="Майнд-карта"]`; hold the 3rd `/full` call (cache key `["session",id]`) | `article.mtg-doc--wide` + `svg.spin` in `div.p-10` | GET /full |
| meetings.detail.mindmap-unavailable | Third `/full` call fails (the first two must succeed) | EmptyState "Карта недоступна" | same |
| meetings.detail.mindmap-private | `ephemeral: true` | "Приватная встреча (no-logs) — карта не строится." | — |
| meetings.detail.mindmap-empty | `map_nodes: []` | "Карта строится из стенограммы встречи." + button "Собрать карту" | — |
| meetings.detail.mindmap-building | Click "Собрать карту"; SSE `event:node data:{type,title,parent_title}` | Button "Собираю карту…" (disabled). Draft `.mtg-map-node` visible with no "Скачать" chip | SSE POST /v1/me/sessions/{id}/regenerate-mindmap/stream |
| meetings.detail.mindmap-failed | SSE 402 / 429, detail `"mindmap_unavailable"`, or `event:error {code}` | `p.mtg-doc-error` "Не удалось собрать карту." or "Собирать нечего: у встречи нет стенограммы либо модель не вернула структуру." | same |
| meetings.detail.mindmap-populated | `map_nodes` non-empty (`MapNode`) | `.mtg-map-node` + SVG links + legend "тема / решение / задача / вопрос" + buttons "Пересобрать карту" and "Скачать" | — |
| meetings.detail.mindmap-download-menu | Click `button[title="Скачать карту"]` | "PNG — картинкой", "SVG — вектор" | — |
| meetings.detail.impact-loading | Click `button[aria-label="Влияние"]` while `/impact` is still in flight | `svg.spin` in `div.p-[40px]` | GET /impact |
| meetings.detail.impact-empty | `GET /impact` → `{items:[]}` | "Встреча ничего не меняет" + "Здесь появятся задачи и сроки, которые встреча предлагает изменить." | same |
| meetings.detail.impact-populated | Items with `status:"suggested"` | `ul.mtg-impact-list > li.mtg-impact[data-decided="false"]`, buttons "Отклонить" and "Применить"; link "Показать цитату" when `evidence_segment_id` is set | same |
| meetings.detail.impact-decided | `status` applied / rejected / approved / failed / superseded | `li[data-decided="true"]` + `.mtg-impact-status` "применено" / "отклонено" / … | — |
| meetings.detail.impact-manual-only | `policy: "never"` | `.mtg-impact-policy` "только вручную" | — |
| meetings.detail.impact-diff | `before_state` / `after_state` with `dueAt` or `due_at` | `.mtg-impact-diff` "Было: …" ("без срока" when one side is missing) | — |
| meetings.detail.impact-apply-error | `POST …/impact/{iid}/apply` → 4xx | `p.mtg-impact-error[role="alert"]` "Не удалось применить. Попробуйте снова." (code-specific text via `apiErrorMessage`) | POST /impact/{iid}/apply, POST /impact/{iid}/reject |
| meetings.detail.processing | `GET /processing` → `{state:"transcribing", attempt:1, stages:[{stage:"transcription",status:"running",…}]}` | `section.mtg-processing` "Идёт обработка" + `li.mtg-stage[data-status=…]` ("Расшифровка", …), "12s". From attempt 2 the label reads "attempt 2" in English — a defect, see Findings | GET /processing (polled every 5 s until a final state) |
| meetings.detail.status-chips | `SessionFull.status` "processing" or "failed"; `ephemeral: true`; `mcp_shared: true` | Chips "Обработка" / "Ошибка обработки" / "Приватная" / "MCP" (`title="Доступ внешним AI открыт"`) | — |
| meetings.detail.private | `ephemeral: true` | No "Поделиться", no "Влияние" chip, no hub chip; chip "Приватная" | — |
| meetings.detail.action-items | `note.actionItems` non-empty, view draft or enhanced | `h2` "Задачи" + "1/3" + `button.mtg-task[aria-pressed]` | PATCH /note/action-items/{aid} on click |
| meetings.detail.title-rename | Click `button.mtg-doc-title` | `input.mtg-doc-title[aria-label="Название встречи"]` | PATCH /v1/me/sessions/{id} |
| meetings.detail.folder-chip / folder-menu | Click the chip "Добавить в папку" (or the folder name) | `.mtg-menu` listing folders (check mark on current), "Папок пока нет — создайте их в библиотеке.", "Убрать из папки" | GET /me/folders; PUT /me/sessions/{id}/folder |
| meetings.detail.hub-chip-unassigned | `GET /hubs/of-meeting/m1` → `null`; hub-suggestion → `null` | Round icon chip `button[aria-label="Отнести к хабу"]` | GET /hubs/of-meeting/{id}, GET /hubs?include_archived=false, GET /me/sessions/{id}/hub-suggestion |
| meetings.detail.hub-chip-suggested | Hint `{hub_id:"h1", signal:"title"}` and `h1` is in `GET /hubs` items | `button[aria-label="Похоже на"]` with a yellow dot | same |
| meetings.detail.hub-chip-assigned | `of-meeting` → HubOut | Chip showing the hub name (red icon if `tracker_project_id` is null) | same |
| meetings.detail.hub-popover | Click the hub chip | `dialog[aria-label="Отнести к хабу"]`: "Похоже на <name>" + "в названии встречи"; "Создать первый" (no hubs); "Открыть дело" / "снять"; "у хаба нет доски" | POST /hubs/{h}/meetings, DELETE /hubs/{h}/meetings/{sid} |
| meetings.detail.export-menu | Click `button[aria-label="Экспорт встречи"]` | Label "Скачать файл" + TXT / MD / SRT / VTT / JSON (client-side download) | — |
| meetings.detail.actions-menu | Click `button[aria-label="Действия со встречей"]` | "Доступ внешним AI (MCP)" + `[role=switch][aria-label="Доступ внешним AI (MCP)"]` + "Claude / Cursor / ChatGPT видят эту встречу" | PATCH /v1/me/mcp/sessions/{id}/share |
| meetings.detail.actions-menu-send | Paid user, and `GET /me/integrations` has `status:"connected"` | Label "Отправить" + provider labels (e.g. "Slack") | GET /me/integrations; POST /me/integrations/{type}/push/{id} |
| meetings.detail.actions-menu-private | `ephemeral: true` | "Приватная встреча (no-logs) — наружу не передаётся." | — |
| meetings.detail.share-loading | Click `button[title="Поделиться результатом встречи"]` ("Поделиться"); hold `/share` | `dialog[aria-label="Поделиться результатом встречи"]` + `svg.spin` | GET /me/sessions/{id}/share |
| meetings.detail.share-private | `{exists:false, visibility:"private", url:null, comments:[], …}` | Options "По ссылке" and "Открытая ссылка"; no URL input | same |
| meetings.detail.share-shared | `visibility:"shared"`, url set, `exists:true` | Read-only URL input + "Скопировать"; toggles "Показывать стенограмму" etc.; "Срок" chips "Бессрочно" / "7 дн." / "30 дн." / "90 дн." (one has `aria-pressed=true`); "Пароль от ссылки" + "Установить пароль"; "Отозвать ссылку" | PUT / DELETE /me/sessions/{id}/share |
| meetings.detail.share-password-set | `has_password: true` | Hint "Пароль установлен. Введите новый, чтобы заменить" + "Снять пароль" | — |
| meetings.detail.share-public | `visibility: "public"` | Same as shared, without the password block | — |
| meetings.detail.share-comments | Live share with `comments` non-empty | "Комментарии (N)" + `button[aria-label="Удалить комментарий"]` | DELETE /share/comments/{cid} |
| meetings.detail.share-copied | Click "Скопировать" (needs clipboard permission) | Button text "Скопировано" for 1.6 s | — |
| meetings.detail.transcript-pill | Default | `button.mtg-dock-pill` "Транскрипт" + "реплик: N" ("пуст" when 0) | — |
| meetings.detail.transcript-open | Click the pill | `.mtg-dock-card` + `input[aria-label="Поиск по транскрипту"]` + `button[aria-label="Свернуть транскрипт"]` | — |
| meetings.detail.transcript-empty | No segments; open the dock | "Транскрипт пуст — расшифровка появится после обработки записи." | — |
| meetings.detail.transcript-search-match | Type into the search field | `.mtg-seg[data-match="true"]` | — |
| meetings.detail.transcript-hover-delete | Hover `.mtg-seg` (hover reveals hidden UI) | `.mtg-seg-drop[title="Удалить реплику"]` at opacity 1 | — |
| meetings.detail.transcript-segment-edit | Click `button.mtg-seg-read` | `textarea[aria-label="Править сегмент"]` | PATCH /me/sessions/{id}/segments/{sid} (autosave 700 ms) |
| meetings.detail.transcript-delete-confirm | Click the trash icon | `dialog[aria-label="Удалить реплику?"]` "Реплика исчезнет из стенограммы…" | DELETE /segments/{sid} |
| meetings.detail.transcript-deeplink | `/app/meetings/m1#seg-s5` | Dock opens on its own; `#seg-s5` scrolled to centre | — |
| meetings.detail.speaker-guess | `/speakers` has `{identity_status:"candidate", identity_name:"Анна"}`; the segment's `speaker_idx` matches | Speaker label "Анна?" + `button[aria-label="Принять: это Анна"]` | PATCH /me/sessions/{id}/speakers |
| meetings.detail.speaker-names-modal | `/speakers` non-empty and segment `speaker_idx` not null; click the label (`title="Переименовать: Спикер 1"`) | `dialog[aria-label="Имена говорящих"]`, `h2` "Кто говорит", hint "Имя подставится во все реплики…" | same |
| meetings.detail.aside | Viewport ≥1360px (rail sidebar; ≥1560px if the sidebar is expanded) and any of: ≥2 speakers, outline items, action items / suggested impact / hub, enhanced headings | `aside.mtg-aside[aria-label="Сводка встречи"]` with cards "Оглавление", "Кто говорит" (percentages), "Что уехало", "В этой встрече" | GET /outline (only when wide) |
| meetings.detail.aside-outline-expanded | `/outline` → `{items:[{kind:"decision",title,start_offset_ms}]}`; click `button.mtg-aside-kind` | `button.mtg-aside-kind[aria-expanded="true"]` + `.mtg-aside-item` showing mm:ss | — |

**Endpoints and response shapes**

On load:
- `GET /v1/me/sessions/{id}/full` is called twice (keys `detail` and `segments`), and a third time on the mindmap tab (key `["session",id]`). Returns `SessionFull` (`types.ts:361`), via `sessions.ts:17`.
- `GET /v1/me/sessions/{id}/note` returns `Note` (`types.ts:50`), via `notesApi.ts:7`.
- `GET /v1/me/sessions/{id}/processing` returns `SessionProcessing | null` (`types.ts:304`), via `sessions.ts:96`.
- `GET /v1/me/sessions/{id}/speakers` returns `SessionSpeaker[]` (`types.ts:281`).
- `GET /v1/me/sessions/{id}/impact` returns `{items: SessionImpact[]}` (`types.ts:315`, `sessions.ts:113`). It is always fetched, because the aside calls it.
- `GET /v1/me/sessions/{id}/outline` returns `{items: SessionOutlineItem[]}` (`types.ts:354`). Only fetched at ≥1360px, not mobile or tablet.
- `GET /v1/me/folders`.
- `GET /v1/hubs/of-meeting/{id}` returns `HubOut | null` (`features/hub/api/hubApi.ts:20`, `:168`).
- `GET /v1/hubs?include_archived=false` returns `{items: HubOut[]}` (`hubApi.ts:48`).
- `GET /v1/me/sessions/{id}/hub-suggestion` returns `{hub_id, signal, confidence} | null` (`hubApi.ts:179`).
- `GET /v1/me/integrations` (paid only) returns `IntegrationConnection[]` (`types.ts:209`).
- `GET /v1/me/templates` returns `Template[]` (`types.ts:194`). Only fetched when the EnhancedMenu chip is mounted.

On demand:
- `GET /v1/me/sessions/{id}/share` returns `MeetingShare` (`contracts/share.ts:12`).

SSE, via `@microsoft/fetch-event-source`. Both send `Authorization: Bearer` from `ensureAccessToken()`, have no auto-retry, and treat a non-OK response as fatal. A 200 is enough; content-type is not checked.
- `notesStream.ts:72` events:
  - `delta {text}`
  - `status {phase}`
  - `warning`
  - `note {Note}` (written into the cache)
  - `mindmap {nodes: MapNode[]}`
  - `error {message}`
  - `done`
- `mindmapStream.ts:78` events:
  - `node {type,title,parent_title}`
  - `status {phase}`
  - `mindmap {nodes}`
  - `error {code}`
  - `done`
- On failure, the UI shows the error text in `p.mtg-doc-error`. A stream that ends without `done` still clears the pending state (`.finally`).

**Hazards**
- CodeMirror editor: blinking caret and selection toolbar. Rename inputs auto-focus and select.
- `formatDateTime` for date chips and impact due dates depends on timezone and locale.
- `/processing` polls every 5 s.
- `useEnhanceStream` flushes text every 80 ms.
- Mindmap layout is pure maths (`model/mindmapLayout.ts`, no DOM measurement, no randomness), but it is wide and needs horizontal scroll.
- The aside uses a `MutationObserver` on headings and `requestAnimationFrame` in `useRaiseOnScroll` (aside top depends on scroll position).
- Dock and modals use `.pop` animations.
- ShareModal: the highlighted expiry chip depends on `Date.now()` (`ShareModal.tsx:50`). "Скопировано" lasts 1.6 s.
- Aside visibility depends on the CSS breakpoint 1360/1560 plus `data-sidebar`.
- Opening any `/full` failure kills the whole page.

---

## /templates

- **Route:** `TemplatesPage`, access `auth` (`feature.ts:94`), inside the shell, under `MeetingsLayout` (subnav tab "Шаблоны" is active).
- **Who sees it:** free and paid users. There is no paywall.
- **Header:** PageHeader №03, eyebrow "Встречи".

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| meetings.templates.loading | Hold GET | `h1` "Шаблоны" + `svg.spin` | GET /v1/me/templates |
| meetings.templates.empty | `[]`, or an error (an error renders as empty) | "Шаблонов пока нет" + "Создайте шаблон, чтобы заметки были в одном формате." | same |
| meetings.templates.populated | `[{id,name,sections,builtin}]` | Rows with "Секций: N"; builtin rows show "Встроенный · …" and `button[aria-label="Настроить под себя"]`; custom rows show `button[aria-label="Редактировать"]` and `button[aria-label="Удалить"]` | same |
| meetings.templates.editor-new | `/app/templates?new=1`, or click "Новый шаблон" | `h1` "Новый шаблон", button "Назад", input labelled "Название шаблона" (placeholder "Например: 1:1"), section "Что обсудили", hint "Дайте шаблону название — без него он не сохраняется." | POST /v1/me/templates (autosave) |
| meetings.templates.editor-edit | Click "Редактировать" | `h1` "Шаблон", populated fields, buttons "Выше" / "Ниже" / "Удалить секцию" / "Добавить секцию" | same |
| meetings.templates.editor-copy-builtin | Click "Настроить под себя" | `h1` "Новый шаблон", name "<name> — моя версия" | same |
| meetings.templates.editor-save-error | POST → 422 `{detail:"too_many_templates"}`, `"builtin_readonly"`, or another error | Red text "Достигнут предел числа шаблонов — удалите ненужные." / "Встроенный шаблон нельзя изменить — создайте на его основе свой." / "Не удалось сохранить. Правка не потеряна — она уйдёт при следующем изменении." | same |
| meetings.templates.delete-error | `DELETE /v1/me/templates/{id}` → error | Toast "Не удалось удалить шаблон. Попробуйте ещё раз." | DELETE |

**Endpoints:** `GET`, `POST {id|null,name,sections}`, and `DELETE /v1/me/templates[/{id}]` (`api/templatesApi.ts:7-23`). Shape is `Template` (`types.ts:194`).

**Hazards:** PageHeader `.rise` animation (360 ms); autosave debounce.

---

## /settings/integrations

- **Route:** `IntegrationsPage`, access `auth` (`feature.ts:93`), inside the shell, under `MeetingsLayout`.
- **Paywall:** paid users only. Free users get `PremiumLocked` (`IntegrationsPage.tsx:46-55`) and no GET is sent.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| meetings.integrations.paywall | Free user | `h1` "Интеграции" + "Нужна подписка" + "«Интеграции» доступна только на платной подписке…" + "Перейти к тарифам" | none |
| meetings.integrations.loading | Paid; hold GET | `svg.spin` under the header | GET /v1/me/integrations |
| meetings.integrations.populated-disconnected | `[]` (an error also renders like this) | 9 cards: Google Drive, Dropbox, Яндекс Диск, Notion, Slack, HubSpot, Attio, Affinity, Zapier. Storage cards show "Подключить через Google Drive (OAuth)"; others show inputs ("Integration token", "Incoming webhook URL", …) and "Подключить" (disabled while empty) | same |
| meetings.integrations.card-oauth | Connection has `oauthAvailable:true` and is not connected | Single button "Подключить через Notion (OAuth)" | GET /me/integrations/{type}/oauth/authorize → `{url}` |
| meetings.integrations.card-connected | `{type, status:"connected", accountLabel, mapping}` | Tag "Подключено" + account label + "Отключить". Storage cards show "Не выгружать сюда" + "Выключает только выгрузку встреч…" | POST /me/integrations/{type}/disconnect |
| meetings.integrations.card-target | Connected hubspot / attio / notion | Input "Запись в CRM" / "ID страницы Notion"; "Сохранить запись" appears when edited | PATCH /me/integrations/{type}/mapping |
| meetings.integrations.card-connect-error | Connect POST → 422 / 502 / other | "Проверьте URL/токен: только https, без внутренних адресов." / "Сервис отказал. Проверьте…" / "Не удалось подключить." | POST /me/integrations/{type}/connect |
| meetings.integrations.storage-waiting | Click storage OAuth: opens a new tab, then connect polls with 409 | Spinner + "Ждём подтверждения доступа…" | POST connect polled every 2 s ×45 |
| meetings.integrations.oauth-toast | `/app/settings/integrations?oauth=notion_ok` (also `notion_err`, `notion_no_page`, `slack_ok`, `attio_ok`, `hubspot_err`, …) | Toast "Notion подключён" / "Не удалось подключить Notion" / "Attio подключён — укажите запись для заметок"; the param is stripped | — |

**Endpoints:** `api/integrationsApi.ts:13-56`. Shape is `IntegrationConnection[]` (`types.ts:209`).

**Hazards:**
- The "Скоро" tag and "soon" branch are dead code: every registry type is supported.
- `window.open` for storage OAuth.
- 2 s polling loop.
- Toast timers.

---

## /r/:token

- **Route:** `SharedMeetingPage`, access `public`, `outsideShell` (`feature.ts:82`). The module is static; its namespace loads lazily.
- **Who sees it:** anyone, with or without login. There is no paywall.
- **Example URL:** `/app/r/tok123`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| meetings.shared.loading | Hold GET | `.shr` with a centred `Card.rise` + `svg.spin` + brand "Whisperer" | GET /v1/meetings/shared/{token} |
| meetings.shared.loading-stuck (bug) | GET → 5xx or network error. `.catch` sets the result to null, so the spinner never ends (`SharedMeetingPage.tsx:107`, `:161`) | Same as loading, permanently | same |
| meetings.shared.password | `{found:false, needs_password:true}` | "Страница защищена паролем", password input labelled "Пароль от ссылки" (autofocus), hint "Его сообщает тот, кто прислал ссылку", button "Открыть" (disabled while empty) | — |
| meetings.shared.password-wrong | Submit; unlock → `{ok:false}` or an error | Input error "Неверный пароль" | POST /v1/meetings/shared/{token}/unlock |
| meetings.shared.unlocked | Unlock → `{ok:true, ticket:"t"}` → re-GET with `?ticket=t` | Populated page | GET …?ticket= |
| meetings.shared.gone | `{found:false}` | "Ссылка недействительна" + "Её отозвали или истёк срок действия" | — |
| meetings.shared.populated | Full `SharedResult` | `h1.shr-title`, kicker "ИТОГ ВСТРЕЧИ · WHISPERER", meta "Дата" / "Длительность" ("N мин") / "Обсуждение", `nav[aria-label="Разделы"]` numbered list. Sections appear only when non-empty: "Итог", "Карта встречи", "Решения", "Задачи", "Ключевые моменты", "Стенограмма", "Обсуждение". CTA "Создано с помощью Whisperer" + "Попробовать Whisperer" | GET + POST /v1/analytics/collect |
| meetings.shared.transcript-truncated | `transcript_truncated: true` | "Показана часть стенограммы" | — |
| meetings.shared.comments-open | `comments.enabled: true` | Inputs "Как вас зовут" and "Комментарий"; button "Отправить" (disabled while empty) | POST /v1/meetings/shared/{token}/comments |
| meetings.shared.comments-closed | `enabled:false` and items non-empty | "Автор закрыл обсуждение" | — |
| meetings.shared.comments-truncated | `total > items.length` | "Показана часть обсуждения — всего реплик: N" | — |
| meetings.shared.comment-failed | Comment POST error | "Не удалось отправить — попробуйте ещё раз" | — |

**Response shapes:** `SharedResult` (`contracts/share.ts:92`), `SharedComment` (`:77`); unlock returns `{ok, ticket?}` (`api/meetingShare.ts:84`).

**Hazards:**
- `img src="/icon-512.png"` is at the origin root, not under `/app`. It is served by the backend (`backend/static`), so it can 404 in a frontend-only harness.
- Dates use `toLocaleDateString` / `toLocaleString` in the reader's locale and timezone.
- `.rise` animation.
- The summary is rendered with `MarkdownMessage`, which pulls in Mermaid (async SVG render; code block first), MathJax and syntax highlighting. These are asynchronous.
- localStorage `shr-author` prefills the name field.
- Mind map is shared with the in-app one.
- External link `https://whisperer.one`.

---

## /calendar

- **Route:** `CalendarPage`, access `auth` (`features/calendar/feature.ts:23`), inside the shell.
- **Who sees it:** free and paid users. The page itself has no paywall.
- **Paid-only parts:**
  - The integrations modal content: free users see only `PremiumBanner` (`ui/integrations/CalendarIntegrations.tsx:207-209`).
  - "Стрим" creation is backend-gated; free users get a toast "Не удалось создать стрим".
- **View and anchor:** both are component state with no URL params. The default is "Месяц" anchored on today.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| calendar.loading | Hold events GET | `svg.spin` in the main column; the sidebar still renders with "Событий пока нет" | GET /v1/me/calendar/events?from=&to= |
| calendar.error | Events → 404 | "Не удалось загрузить события" + button "Повторить" | same |
| calendar.month.empty | `[]` | Month grid of 42 `button[aria-label="Добавить событие"]`; today's number has `bg-foreground`; sidebar "Событий пока нет" + "Добавить", "Нет предстоящих" | same |
| calendar.month.populated | Events in range | `button.cal-ev[data-type="meeting"]` (text "10:00 Title"); `aria-label` = title | same |
| calendar.month.overflow | More than 3 events on one day | Button "+N" | — |
| calendar.week | Click the toggle button "Неделя" (`aria-pressed`) | Sticky header with 7 day buttons, hour slots `button[aria-label="07:00"]`, red now-line (`bg-[var(--red)]`) on today | GET events (week range) |
| calendar.day | Toggle "День", or click a week header day | Single column of hour slots, no sticky header | GET events (day range) |
| calendar.zoom | Viewport ≥1560px, view week or day | `input[type=range][aria-label="Zoom"]` + "100%" | — |
| calendar.toolbar-compact | Viewport ≤1360px / ≤1200px / ≤900px | Square icon buttons `[aria-label="Интеграции"]`, `[aria-label="Встреча"]` with `data-onboarding="calendar-meet"`, and "Стрим" | — |
| calendar.sidebar-day-events / sidebar-upcoming | Events on the selected date or in the future | Headings "События дня" / "Ближайшие" with `EventRow` items | — |
| calendar.mobile | Viewport ≤860px | No sidebar | — |
| calendar.context-menu-slot | Right-click a month cell or an hour slot | Single item "Добавить" | — |
| calendar.context-menu-event | Right-click an event | Items "Открыть" and "Удалить" | DELETE /v1/me/calendar/events/{id} (optimistic) |
| calendar.event-modal-new | Click an hour slot / month day / sidebar "Добавить" | `dialog[aria-label="Новое событие"]`; fields "Название", "Дата" (button), "Тип" = "Встреча", toggle "Видеоконференция" ("Выкл"), "Место или ссылка", "Описание", "Участники", "Напоминания", "Связанная встреча" ("Без связи"); Save disabled | GET /v1/me/sessions?limit=50 |
| calendar.event-modal-video-on | Click "Видеоконференция" | `button[aria-pressed="true"]` with "Вкл" | — |
| calendar.event-modal-stream-type | Choose "Стрим" in the "Тип" select | Hint "Создастся трансляция со сценой и залом — откроется студия ведущего." | Save → POST /v1/me/streams |
| calendar.event-modal-validation | End time before start, or title longer than 256 chars | "Окончание должно быть позже начала" / "Слишком длинное название" | — |
| calendar.event-date-popover | Click `button[aria-label="Дата"]` | Radix popover inside the dialog: 2-month day picker + `input[aria-label="Время начала"]` and `input[aria-label="Время окончания"]` | — |
| calendar.event-modal-edit | Click an existing event | `dialog[aria-label="Событие"]` + danger "Удалить" | PATCH /v1/me/calendar/events/{id} |
| calendar.event-modal-meeting | Event with `meeting {room_id, invite_url,…}` | Buttons "Присоединиться" and "Скопировать ссылку" | — |
| calendar.event-modal-stream | `event_type:"stream"` with `meeting.stream_id` | "Открыть студию", "Ссылка для зрителей", "Тип" select disabled | — |
| calendar.event-modal-session-link | `session_id` set | Link "Открыть запись встречи →" | — |
| calendar.event-delete-confirm | Modal "Удалить" | `dialog[aria-label="Удалить"]` "Удалить это событие безвозвратно?" | DELETE |
| calendar.integrations-paywall | Free user; click "Интеграции" | `dialog[aria-label="Интеграции"]` + "Нужна подписка" + "«Интеграции» доступна только на платной подписке…" | none |
| calendar.integrations-loading | Paid; hold GET | `svg.spin` in the modal | GET /v1/me/calendar/integrations |
| calendar.integrations-populated | `[]` (an error also renders like this) | Intro "Подключите внешний календарь…", cards "Google Календарь" / "Microsoft 365 / Outlook" (button "Подключить") / "CalDAV (Яндекс / Nextcloud / iCloud)" (form "Адрес сервера (URL)", "Логин", "Пароль приложения"), each tagged "Не подключено"; section "Подписка (iCal)" | + GET /v1/me/calendar/ical-token |
| calendar.integrations-connected | Connection `{id, provider:"google", calendars:[…]}` | Tag "Подключено", "Календари" checklist with "основной" / "сделать основным", buttons "Синхронизировать" and "Отключить" | GET /v1/me/calendar/integrations/{id}/calendars |
| calendar.integrations-disconnect-confirm | Click "Отключить" | "Календарь перестанет синхронизироваться. Уже перенесённые события останутся." | DELETE /me/calendar/integrations/{id} |
| calendar.integrations-caldav-error | CalDAV connect POST error | "Не удалось подключиться — проверьте адрес и данные" | POST /…/caldav/connect |
| calendar.ical-rotate-confirm | Click "Перевыпустить" | "Перевыпустить ссылку? Прежняя перестанет работать." | POST /me/calendar/ical-token/rotate |
| calendar.stream-modal | Click "Стрим" | `dialog[aria-label="Новый стрим"]`, "Название" (placeholder "О чём эфир", autofocus), "Описание", "Отменить", "Создать стрим" (disabled while empty) | POST /v1/me/streams |
| calendar.toasts | Save, delete, meet error, copy | "Событие сохранено" / "Не удалось сохранить событие" / "Событие удалено" / "Не удалось начать встречу" / "Ссылка скопирована" | — |

**Endpoints and response shapes**
- `features/calendar/api/calendar.ts:10-45`:
  - events: `CalendarEvent[]` (`contracts/types.ts:31`)
  - `POST /v1/me/calendar/meet-now` → `MeetNowResult` (`:80`)
  - ical token → `IcalToken` (`:84`)
- `api/sync.ts:9-48`: `CalendarConnection` (`:98`), `AccountCalendar` (`:108`).
- `POST /v1/me/streams` → `StreamOverview` (`features/streams/contracts/types.ts:74`, `streams/api/streams.ts:58`).
- `POST /v1/me/onboarding/progress` after create or meet.

**Hazards**
- Anchor, `from`/`to` params and "today" all come from `new Date()` and the local timezone (`hooks/useCalendarNav.ts:46`, `model/grid.ts:171`). Mocks should match on path only.
- Weekday and period labels use `Intl` in the locale.
- Now-line position plus a 60 s `setInterval` (`ui/views/TimelineGrid.tsx:13-16`).
- Timeline auto-scrolls to 07:00 on mount.
- "Ближайшие" filters against now.
- New-event default times come from now.
- `Intl…resolvedOptions().timeZone` is sent in the payload.
- "Встреча" opens a popup via `window.open("about:blank")`.
- Bug: `window.open` / `location` paths `/rooms/{id}` and `/studio/{id}` lack the `/app` prefix (`CalendarPage.tsx:71`, `EventModal.tsx:115,140,145`, `StreamModal.tsx:205`).
- The `?oauth=ok|err` toast only fires once the Integrations modal is open (`CalendarIntegrations.tsx:195-205`).
- `.pop` animations.

---

## /context

- **Route:** `ContextPage`, access `auth` (`features/context/feature.ts:24`), inside the shell.
- **Paywall:** paid users only. Free users get `PremiumLocked` №08, eyebrow "Студия", title "Контекст" (`pages/ContextPage.tsx:66-75`), and the GET is disabled.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| context.paywall | Free user | `h1` "Контекст" + "Нужна подписка" | none |
| context.loading | Paid; hold GET | `h1` "Контекст" + `svg.spin` in `div.p-20` | GET /v1/admin/context |
| context.populated | `{id, text:"…", roles:["responses"], files:[…]}` | `textarea[data-onboarding="context-editor"]`, header "Блок контекста", counters "Слов:", "Токенов: ~", "Символов: N / 32 768"; card "Файлы в контексте"; card "Куда подмешивается" with tags (`aria-pressed`) "Ответы в эфире", "Код", "System Design", "Скриншоты", "Leo" | same |
| context.empty | `{text:"", roles:[], files:[]}`. A GET error renders identically | Placeholder "Расскажите, кто вы и как отвечать…", "Пока пусто." | same |
| context.files-tree | Files whose `filename` contains "a/b.txt" | Dir rows `button[aria-expanded="true"]` with folder icon, nested `.border-s-[1.5px]` | — |
| context.saving / saved | Type in the textarea (saves after 800 ms) | Header "Сохраняем…" + spinner, then "Сохранено" for 2 s | PUT /v1/admin/context |
| context.uploading | Pick files via hidden `input[aria-label="Загрузить файлы контекста"]` or `input[aria-label="Загрузить папку контекста"]` | Spinner in the "Файлы" button; both buttons disabled | POST /v1/admin/context/files |
| context.too-large-toast | Selection totals more than 5 MB | Toast "Общий размер файлов — X МБ, это больше лимита 5 МБ. Загрузка отменена." | — |

**Endpoints:** `features/context/api.ts:5-35`. Shapes are `UserContextOut` and `ContextFile` (`contracts/types.ts:4,12`). Roles toggle with `PUT /admin/context/roles`; file delete is `DELETE /admin/context/files/{id}`. A prefetch on nav hover fires for paid users only (`feature.ts` prefetch).

**Hazards:**
- `.rise` animation.
- 2 s "saved" timer.
- Dates via `formatDateTime` (timezone).
- The delete-file `IconButton` has no title or aria-label; select it via the row.
- No error UI at all.

---

## /knowledge-base

- **Route:** `KnowledgeBasePage`, access `auth` (`features/knowledge/feature.ts:19`), inside the shell.
- **Paywall:** paid users only. Free users get `PremiumLocked` №06, eyebrow "Студия", title "База знаний"; all GETs are disabled.
- **URL params:** `?tab=files|sources` and `&doc=<id>`.

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| kb.paywall | Free user | `h1` "База знаний" + "Нужна подписка" | none |
| kb.quota | Space `{used_bytes, limit_bytes, used_ratio:0.4,…}` | Header action "Занято X из Y" + bar | GET /v1/knowledge/space |
| kb.quota-almost-full | `used_ratio ≥ 0.9` | Red bar + "Место почти закончилось" | same |
| kb.not-ready | `ready: false` | Card "Раздел ещё не готов принимать данные: подключите первый источник или загрузите файл." | same |
| kb.files.loading | Hold documents GET | Tabs (`button[aria-pressed]` "Файлы" / "Источники") + spinner in the "Загруженные файлы" card | GET /v1/knowledge/documents |
| kb.files.empty | `[]`; an error renders the same | "Пока ничего не загружено", subtitle "Всего документов: 0" | same |
| kb.files.populated | Documents with status indexed / pending / failed | Rows `#kb-doc-<id>` with tags "Готов" / "Индексируется" / "Ошибка", size and date, `button[aria-label="Удалить"]` | same |
| kb.files.highlight | `/app/knowledge-base?tab=files&doc=d1` | `#kb-doc-d1.border-primary` (smooth-scrolled) | — |
| kb.files.dragover | Drag files over the dropzone | Dropzone `border-foreground bg-primary/15` | — |
| kb.files.packing | Pick a folder (zip being built) | Button "Упаковываем…" + spinner | — |
| kb.files.upload-panel | Pick files | `aside[aria-label="Загрузка файлов"]` "Загрузка N%", then "Все файлы загружены"; error toasts such as "Не хватает места в базе знаний" | POST /v1/knowledge/documents (one per file) |
| kb.sources.loading | `/app/knowledge-base?tab=sources`; hold catalog or sources | Card with spinner | GET /v1/knowledge/catalog, GET /v1/knowledge/sources |
| kb.sources.empty | sources `[]` | "Пока ни одного источника" + catalog cards grouped by "Общение", "Документы", … | same |
| kb.sources.populated | Sources with status active / paused / pending / error / quarantined | Rows: tag "Активен" / "Пауза" / "Подключается" / "Ошибка" / "Остановлен"; "Пауза" / "Возобновить"; `button[aria-label="Обновить"]`, `button[aria-label="Отключить"]`; quarantine text "Источник остановлен: расхождение в настройке…" or `last_error` | same (polled every 5 s while any source is pending) |
| kb.sources.syncing | Click "Обновить" | Refresh icon `.animate-spin` on that row | POST /sources/{id}/sync or /fetch |
| kb.sources.catalog-filter | Type into "Найти источник" | Filtered groups | — |
| kb.sources.catalog-disabled | Spec `available:false` (auth oauth or planned) or kind already connected | Card `opacity-45` with "Скоро: нужен вход через провайдера" / "Скоро: своя интеграция в разработке" / "Подключено" | — |
| kb.sources.disconnect-confirm | Click trash | `dialog[aria-label="Отключить"]` "Отключить «X»? Проиндексированные материалы перестанут находиться." | DELETE /v1/knowledge/sources/{id} |
| kb.connect.form | Click a token / basic / none spec. At the pinned commit only "Веб-сайт" (`web`, field `base_url`) has a form; Jira and the rest are OAuth | `dialog[aria-label="Подключение: Веб-сайт"]`, "Название", fields (labels are raw field names), "Подключить" / "Подключаем…" | POST /v1/knowledge/sources |
| kb.connect.form-error | POST → `{detail:"missing_field:api_token"}` or another code | "Заполните поле «api_token»" / "Не удалось подключить источник" / … | same |
| kb.connect.push-pending | Click a push spec (Obsidian); the POST fires immediately | Spinner + "Ничего вводить не нужно: заметки присылает плагин…" | same |
| kb.connect.push-token | POST → `{…, push_token:"abc"}` | `dialog[aria-label="Obsidian: хранилище подключено"]`, `code` token, "Скопировать", "Токен показывается один раз…", steps 1-3, link "Открыть в каталоге", "Готово" | — |
| kb.connect.oauth-intro | Click an oauth spec | Description (`kb.sources.oauth.about.<kind>`) + "Открыть Google Drive" | POST /v1/knowledge/sources/oauth-session?kind= |
| kb.connect.oauth-waiting | After the open (409 while waiting) | Spinner + "Ждём подтверждения доступа…" | GET /v1/knowledge/sources/oauth-folders?kind= (every 2 s ×90, and on focus) |
| kb.connect.oauth-folders | Folders → `[{id,name}]`; pick one | Select "Что индексировать" ("Выберите из списка"), "Считаем объём…", then "N файлов, X — свободно Y" (+ "не влезает в квоту") | GET …/oauth-preview?kind=&folder_id= |

**Endpoints:** `features/knowledge/api.ts:13-121`. Shapes:
- `KnowledgeSpace` (`contracts/types.ts:75`)
- `KnowledgeDocument` (`:65`)
- `ConnectorSpec` (`:36`)
- `KnowledgeSource` (`:54`)
- `ConnectedSource` (`:94`)
- `OAuthSession` (`:98`)
- `DriveFolder` (`:105`)
- `FolderPreview` (`:107`)

**Hazards:**
- `.rise` on cards and the header.
- Document dates use `toLocaleDateString`.
- Highlight scroll waits 120 ms and is smooth.
- Polling: sources every 5 s, OAuth folders every 2 s.
- Brand marks are data-URI images with `decoding="async"`.
- The upload panel is an app-root widget.
- `window.open` for OAuth.

---

## Search palette (no route — shell slot)

- **Mount point:** `shellSlots` `search-palette` (`features/search/feature.ts:27`).
- **Available on:** every inside-shell route, for any authed user. There is no paywall.
- **Open it with:** `Ctrl+K` or `Meta+K` on any shell page, or the sidebar search button (`[data-onboarding="sidebar-search"]`).

| state id | how to reach | marker | endpoints |
|---|---|---|---|
| search.palette.open-idle | Press Ctrl+K | `dialog[aria-label="Командное меню"]`, `input[aria-label="Поиск команды"]` (placeholder "Введите команду или поиск…"), groups "Навигация" (Встречи, Активность, Перейти в Промпты, …) and "Действия" ("Переключить тему"), footer "Найдено: 12" (13 for admins, who also get "Перейти в Деньги") | — |
| search.palette.too-short | Type one character that matches no command, e.g. "щ" | "Введите минимум 2 символа" | — |
| search.palette.searching | Type ≥2 chars matching no command; hold the GET | "Ищем…" | GET /v1/me/search?q=&per_domain=5&domains=hubs,meetings,tracker,calendar,prompts,context,files,support,models |
| search.palette.results | Hits `[{domain:"meetings", id, title, subtitle, snippet, to, icon}]` | Group headers from `search.domain.*` ("Встречи", "Трекер", …); the active row has `bg-primary` and a chevron | same + the documents call |
| search.palette.knowledge-loading | Hold the `domains=documents` call | Row "Ищу в базе знаний…" + spinner | GET /v1/me/search?…&domains=documents |
| search.palette.knowledge-failed | documents → error, or `unavailable:["documents"]` | "База знаний не ответила — результаты из неё не показаны" | same |
| search.palette.empty | Both calls → `hits:[]` | "По запросу «xyz» ничего не нашли. Попробуйте короче." | both |

**Endpoint:** `features/search/api.ts:4-17`. Shape is `GlobalSearchOut` (`contracts/types.ts:29`).

**Hazards:**
- 220 ms debounce.
- Input focused after 10 ms (caret).
- Hovering a row sets the active row (`onMouseMove`), so pointer position changes which row is highlighted.
- `placeholderData` keeps previous results visible.
- `.pop` animation.

---

## Redirect-only routes

| path | target | declared |
|---|---|---|
| `/meetings/live` | `/meetings` | `meetings/feature.ts:91` |
| `/import` | `/meetings` | `meetings/feature.ts:92` |
| `/rooms` (exact path only; `/rooms/:id` belongs to the rooms feature) | `/calendar` | `calendar/feature.ts:27` |

All three use `RedirectTo` with `replace` and no `keepSearch` (`app/router/guards.tsx:48-52`).

---

## Cross-cutting notes

- **Silent error branches** — these render like empty, so an error state cannot be distinguished visually:
  - `/templates` list
  - `/settings/integrations` list
  - `/context` GET
  - KB documents / sources / catalog
  - Calendar integrations and iCal
  - Folder tree
  - Detail-page segments (`segments.data ?? []`)
  - Search fast-domain failure
- **Dead or unreachable states:**
  - `ImpactView`'s private branch: the "Влияние" chip is hidden when `ephemeral`.
  - The integrations "Скоро" tag: every registry type is supported.
- **Onboarding anchors on these screens:**
  - `[data-onboarding="meetings-nav"]`, `"meetings-upload"`, `"calendar-meet"`, `"calendar-stream"`, `"context-editor"`, `"page-header"`, `"sidebar-search"`.
  - The tour and welcome modal (`features/onboarding`, `GET /v1/me/onboarding`) can overlay any of these pages. Mock that endpoint as completed or skipped.
- **App-wide overlays that can intrude:**
  - Toasts: `role=alert` / `status`, with an auto-hide progress-bar animation.
  - Upload panel `aside[aria-label="Загрузка файлов"]`.
  - Connection-lost overlay (network errors trigger the `/health` probe).
- **Global animation classes used here:** `.rise` (360 ms), `.pop` (180 ms), `.spin` (infinite), `animate-spin`. Consider injecting `* { animation: none !important; transition: none !important }` and freezing `Date`/timezone; calendar, library grouping, now-line and share expiry depend on them.
- **Fixtures:** a ready-made seed exists in `features/meetings/__fixtures__/fixtures.ts` (`createSeedData`) and `mockProvider.ts`, usable as a template for meetings data.
- **Viewport breakpoints:**
  - Mobile ≤860px; tablet 861–1024px (`shared/hooks/useMediaQuery.ts:21-27`).
  - Meeting aside ≥1360px (rail sidebar) or ≥1560px (full sidebar).
  - Calendar toolbar compaction at 1560 / 1360 / 1200 / 900px.
  - Pick fixed viewports per state.

### Findings (step 4 of D2)

Draft defects visible on screen. By decision 4 of the D2 plan they stay out of the baseline, and v2 shows the intended text.

1. **The AI version stream loses its error text.** On 402, 429 or a dropped connection, `notesStream` reports the specific message («Исчерпан лимит минут тарифа.», «Слишком много запросов…», «Соединение прервано.»). Then `useEnhanceStream`'s `.catch` overwrites it with the generic «Не удалось собрать AI-версию.» (`frontend/src/features/meetings/hooks/useEnhanceStream.ts:126`).
2. **Russian plural forms are missing for «попытка».** The ru catalog has only `attempt_one` and `attempt_other`. Russian `2` needs `few`, so i18next falls back to English and shows «attempt 2» on the processing panel (`features/meetings/locales/ru.json`, `meet.detail.processing.attempt`).
3. **A private meeting offers to send itself out.** The actions menu of an `ephemeral` meeting lists «Отправить» → Slack / Notion next to «Приватная встреча (no-logs) — наружу не передаётся».
4. **The shared page logo lives outside the SPA.** `SharedMeetingPage` loads `/icon-512.png` from the site root, which only the backend serves. This is not a defect of the screen, but the harness must serve the draft's root icons (`scripts/export-draft.sh`).
5. **The shared page spins forever on a failed request.** When `GET /v1/meetings/shared/{token}` answers 5xx or the network fails, `.catch` sets the result to `null` and the spinner never ends (`SharedMeetingPage.tsx:107`, `:161`). Out of the baseline; v2 shows an error. Recorded in step 8 of D2, when the inventory coverage check found the row without a decision.

### Coverage in the screenshot matrix (step 4 of D2)

**Captured inside another state:**

| state | screenshot |
|---|---|
| `meetings.library.card-variants`, `folders-populated`, `folders-favorites`, `import-idle` | `meetings.library.populated` |
| `meetings.library.folders-empty` | `meetings.library.empty` |
| `meetings.library.mobile-folders-collapsed` | the mobile cells of `meetings.library.populated` |
| `meetings.library.import-refusal-client`, `import-refusal-server` | `meetings.library.import-refusal-format`, `-empty`, `-too-large`, `-quota`, `-rate`, `-storage`, `-no-logs` |
| `meetings.detail.impact-decided`, `impact-manual-only`, `impact-diff` | `meetings.detail.impact-populated` |
| `meetings.detail.status-chips` | `meetings.detail.processing`, `status-failed`, `private`, `enhanced` (MCP) |
| `meetings.detail.action-items`, `transcript-pill`, `aside`, `hub-chip-assigned`, `folder-chip` | `meetings.detail.enhanced` |
| `meetings.detail.hub-chip-suggested` | `meetings.detail.draft` |
| `meetings.detail.hub-chip-unassigned` | `meetings.detail.draft-placeholder` |
| `meetings.detail.share-shared` | `meetings.detail.share-password-set` |
| `meetings.detail.share-comments` | `meetings.detail.share-public` |
| `meetings.detail.speaker-guess` | `meetings.detail.transcript-open` |
| `meetings.templates.editor-save-error` | `meetings.templates.editor-save-error-limit`, `-builtin`, `-generic` |
| `meetings.integrations.populated-disconnected` | `meetings.integrations.disconnected` |
| `meetings.integrations.card-connected`, `card-target` | `meetings.integrations.populated` |
| `meetings.integrations.card-connect-error` | `meetings.integrations.connect-error-validation`, `-upstream`, `-generic` |
| `meetings.integrations.oauth-toast` | `meetings.integrations.oauth-toast-ok`, `-attio`, `-error` |
| `meetings.shared.comments-open` | `meetings.shared.comment-failed` (the form, scrolled into view) |
| `calendar.month.overflow`, `calendar.sidebar-day-events`, `calendar.sidebar-upcoming` | `calendar.month.populated` |
| `calendar.mobile`, `calendar.toolbar-compact` | the mobile cells of the calendar states (compaction below 900 px) |
| `calendar.event-modal-edit` | `calendar.event-modal-meeting`, `-stream`, `-session-link` |
| `calendar.ical-rotate-confirm` | `calendar.integrations-ical-rotate-confirm` |
| `calendar.toasts` | `calendar.toast-saved`, `toast-save-error`, `toast-deleted`, `toast-delete-error`; the meet and copy toasts need LiveKit and the clipboard |
| `context.files-tree` | `context.populated` |
| `kb.quota` | `kb.files.populated` |
| `kb.sources.catalog-disabled` | `kb.sources.populated` (connected kinds are disabled) |
| `search.palette.*` | `shell.palette.open`, `too-short`, `searching` (with `knowledge-loading`), `empty`, `kb-unavailable`, `results` |

**Not screenshotted:**

| state | reason |
|---|---|
| `meetings.layout.chunk-loading` | a lazy chunk loading; the harness serves chunks from disk at once and overrides only `/v1` |
| `meetings.detail.share-copied` | lives 1.6 s on a real timer and needs clipboard permission |
| `meetings.detail.enhanced-error` for 402, 429, a drop; `actions-menu-private`; the «попытка N» label | draft defects (Findings 1–3) |
| `meetings.shared.loading-stuck` | draft defect (Finding 5) |
| `context.saved` | «Сохранено» lives 2 s on a real timer |
| `calendar.zoom` | needs a viewport of 1560 px or wider; the matrix desktop is 1440 px |
| `kb.files.packing` | lasts only while the browser zips a picked folder |

Step 5 added replay of open SSE streams. The two streaming states deferred above are now captured as their own states: `meetings.detail.enhanced-streaming` (text arriving, no end of stream yet) and `meetings.detail.mindmap-building-nodes` (draft nodes arriving).
