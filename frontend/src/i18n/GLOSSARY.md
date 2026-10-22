# Studio glossary and style guide

How Studio speaks in every interface language. `npm run i18n:check` enforces the parts marked **checked**.

- English is the source. Catalogs: `messages/<language>/<namespace>.json`.
- Terms: `glossary/terms.md` lists every concept the interface names; `glossary/<language>.md` gives the one
  word to use for each, and the words never to use (**checked**: a catalog may not contain an "Avoid" word,
  except inside the language's quotation marks, where another product's own label is cited as it reads there:
  macOS's 「アプリケーション」 folder).
- The admin panel (`/admin`) is written in Russian only and is not part of these catalogs.

## Voice

Studio sounds like a calm, competent colleague: short, plain, human. Translate the meaning, not the words.

- **Short.** Say it in as few words as the language allows. A button is one or two words.
- **Plain.** Everyday words over jargon. No marketing tone, no exclamation marks (greetings aside).
- **Consistent.** One concept, one word, on every screen: take it from the language's glossary.
- **Buttons are actions:** a verb or the language's usual command form ("Save", "Add task").
- **Errors say what failed and, when it helps, what to do**, without blaming the user:
  "Couldn’t save. Check your connection." Never "Error!", "Oops", "Failed to…".
- **Empty states say what will appear and how to start:** "No files yet" + "Upload a file to get started."
- **Sentence case** in every language that has letter case: "Add task", not "Add Task".
- **Leo speaks for itself** in the first person ("I can’t read inside files yet"); the interface never says "I".

## Do not translate

Names and identifiers stay exactly as written, in Latin script, in every language (**checked**: when the
English text contains one, the translation must contain it too). Grammar around them follows the language.

- `Leo`
- `Studio`
- `Claude`
- `GPT Astra`
- `Slack`
- `Telegram`
- `Notion`
- `GitHub`
- `GitLab`
- `Google Drive`
- `Google Workspace`
- `Google Meet`
- `Zoom`
- `Microsoft Teams`
- `Gmail`
- `Outlook`
- `Dropbox`
- `Confluence`
- `Jira`
- `HubSpot`
- `WhatsApp`
- `LiveKit`
- `DeskTime`
- `Shosai`
- `skills.sh`
- `SKILL.md`
- `MCP`
- `OAuth`
- `Markdown`

Plan names (`Free`, `Pro`, `Team`, `Enterprise`) are names too: they stay in Latin script, while the word "plan"
around them is translated. The audience tabs of the upgrade screen (Individual, Team, Enterprise) are ordinary words
and are translated. Also untouched: model and provider names from the API, file extensions (`.pdf`), keyboard keys (`⌘`, `Ctrl`),
codes, IDs, URLs, e-mail addresses, and anything users typed (names of tasks, files, boards, people).

## Messages, variables and plurals

- Keep `{placeholders}` exactly; move them where the language needs them. Never translate their names.
- Plurals use ICU: `{count, plural, one {# file} other {# files}}`. Write every category the language has
  (**checked**): ru one/few/many/other; ar zero/one/two/few/many/other; fr, es, it, pt-BR one/many/other
  ("many" is for very large numbers: "1 000 000 de fichiers"); ja, ko, zh-Hant, vi, id only other. `=0` is
  allowed on top. Never build a plural by adding letters in code.
- `select` keys are codes: keep them, translate only the text.
- Rich text tags (`<link>…</link>`, `<b>…</b>`) stay; translate the text inside and move the tag with it.
- Dates, times, numbers, sizes, currencies and units are never written into a message: they arrive as
  formatted arguments (`{date}`), or as ICU `{count, number}` / `{when, date, short}`. No "12/31", no "$".
- Whole sentences only. A message is never glued from fragments, so every language can order its words.

## Text written by Leo

Leo's answers, summaries, triage notes, briefs and drafts are written by the model in the user's language
(Settings › Leo › Response language, "Auto" = the interface language). They never pass through these
catalogs. Only the interface around them is translated: buttons, labels, statuses, errors.

## Demo content

Translate what the product itself defines: statuses, priorities, default names ("Untitled folder"), empty
states, suggestions, onboarding hints. Do not translate what a user or the backend would have written: task
and file names, notes, emails, chat messages, people, companies, and the rows of large demo tables.

## Typography by language

The **Not allowed** characters are **checked** in the text of every message (not in ICU syntax). Everywhere:
the ellipsis is one character `…`, never `...`; the apostrophe is `’`, never `'`.

| Code | Address the user | Quotes | Not allowed | Notes |
| --- | --- | --- | --- | --- |
| en | you | “…” ‘…’ | `"` | Sentence case. |
| fr | vous | « … » | `"` `“` `”` | No-break space before `: ; ! ? »` and after `«` (**checked**). |
| de | du | „…“ | `"` `”` `«` `»` | Nouns capitalised as German requires; avoid long compound chains in buttons. |
| ru | вы (lowercase) | «…» „…“ | `"` `”` | ё where it matters for meaning (ещё, всё); short imperative buttons. |
| nl | je | ‘…’ “…” | `"` `«` `»` | |
| it | tu | «…» “…” | `"` | |
| es | tú | «…» “…” | `"` | Neutral Spanish, no regionalisms; plural "you" is ustedes. Opening ¿ ¡. |
| pt-BR | você | “…” | `"` `«` `»` | Brazilian vocabulary and spelling (arquivo, tela, usuário). |
| ar | neutral | «…» | `"` `“` `”` `,` `?` `;` | Use ، ؟ ؛. Buttons as verbal nouns (حفظ, إلغاء) so they fit any gender. Modern Standard Arabic. |
| tr | siz | “…” | `"` `«` `»` | Suffixes after names: Leo’ya, Notion’a (with ’). |
| ko | no pronoun | “…” ‘…’ | `"` `「` `」` | 해요체 in messages, noun forms on buttons (저장, 취소). Avoid 당신. |
| hi | आप | “…” | `"` | Devanagari; end sentences with । (**checked**). Common English tech words may stay in Latin if Hindi UIs use them. |
| vi | bạn | “…” | `"` | |
| zh-Hant | 你 | 「…」『…』 | `"` `“` `”` | Taiwan vocabulary (檔案, 資料夾, 設定, 帳號); full-width ，。：；？！ (**checked**). |
| ja | no pronoun | 「…」『…』 | `"` `“` `”` | です・ます in messages, short noun or verb forms on buttons; full-width 、。 (**checked**). |
| id | Anda | “…” | `"` | |

## Length and layout

German, French and Russian run about 30% longer than English, Japanese and Chinese about 40% shorter but
taller. Keep buttons, tabs and table headers short; prefer a shorter synonym over abbreviations. Arabic is
right to left: never put direction words ("on the left") into a message.

## Review

Each language needs a native speaker's read of every new namespace before release. Raise a term change in
the language's glossary file first, then update the catalogs, so the whole product moves together.
