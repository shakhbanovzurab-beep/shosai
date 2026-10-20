# Notes API

The contract between Notes (`/app/notes`, a meeting's page `/app/notes/{id}`), the home screen's recent notes and
the backend's `notes` slice ([notes plan](../../docs/plan/slices/notes.md),
[ADR 0057](../../docs/adr/0057-notes-and-meetings-slice-names.md)). The OpenAPI schema is the source of truth:
`src/lib/api/generated/schema.d.ts`. The slice calls `/v1/*` through the typed client in its `api/` layer; its
`model/` maps the snake_case shapes to the camelCase ones the screens use (`model/library-cards.ts`,
`model/meeting-resource.ts`, `model/write-up.ts`). Errors use the platform envelope `{error: {code, params?}}`
(ADR 0008); `domain/problems.ts` lists the codes the interface words in the person's language, and any other code
shows the server's text with the request id.

The share link and its comments (`ShareLinkPanel`, the public page) still run on the slice's mocks until step 19 of
the plan; nothing else in Notes has sample data.

## Routes

| Method | Path | Used by |
|---|---|---|
| `GET` | `/v1/notes?folder=&cursor=&limit=` | The library, 50 a page (`folder`: a folder's id, or `none` for meetings in none); the home screen's four recent notes |
| `GET` | `/v1/notes/counts` | The folder pills: every meeting the person may read, and their own per folder |
| `GET` | `/v1/notes/{id}` | A meeting's page; its route loader, so an unknown or foreign meeting is the 404 page |
| `PATCH` | `/v1/notes/{id}` | Filing a meeting in a folder (`folder_id`, `null` for none) |
| `DELETE` | `/v1/notes/{id}` | Delete; the library hides the card at once and sends the request when the Undo toast closes |
| `GET`, `POST`, `PATCH`, `DELETE` | `/v1/notes/folders[/{id}]` | Folders: list, create (the server picks the colour), rename, delete |
| `GET` | `/v1/notes/{id}/transcript?cursor=&limit=500` | The transcript tab and the export, read page by page to the end |
| `GET` | `/v1/notes/{id}/write-up` | Leo's notes laid out by their template; `404 write_up_not_found` means none yet |
| `POST` | `/v1/notes/{id}/write-up` | Rewrite with another template or again (`Idempotency-Key`); answers the run to follow |
| `GET` | `/v1/notes/{id}/map?cursor=&limit=100` | The mind map's nodes in pre-order, built into a tree in `domain/mind-map-tree.ts` |
| `GET`, `PUT` | `/v1/notes/{id}/my-notes` | The person's own notes, autosaved |
| `POST`, `DELETE` | `/v1/notes/{id}/participants[/{pid}]` | Add a person by address; remove one added by hand |
| `GET`, `POST` | `/v1/notes/templates` | Shipped templates by their codes and the person's own; create one |
| `POST` | `/v1/me/uploads…` (purpose `recording`), then `/v1/notes/imports` | Upload a recording, then claim it as a meeting |
| `GET` | `/v1/me/runs/{id}` | A run's state and failure code: the rewrite's wait and the page's notices |

## Behaviour the UI relies on

- **Paging.** The library reads the first page at once and the next ones with "Show earlier meetings". While a
  meeting is live or its notes are being written, the first page is read again every 1.5 s; pages read further are
  kept under it (`model/library-resource.ts`, `merged`). The counts are read once and after each change.
- **Who may change what.** Only the owner files and deletes a meeting (`owned`); `manageable` decides adding and
  removing people, rewriting the notes and the template menu. A workspace's meeting shows no folder picker.
- **Uploads.** A recording goes straight to the home's bucket through the shared upload client
  (`src/lib/uploads/`, FL-D1), two files at a time, then `POST /v1/notes/imports` claims it and the meeting appears
  with its processing status. A failed upload stays a row with its reason until the person removes it. In the grid
  of all meetings the first upload takes the large "latest meeting" card at once, under the name the server gives
  its meeting (the file's name without its extension); once the import answers, the upload knows its `meeting_id`
  and hides in the frame its meeting arrives, so only that card's content changes and nothing below it moves.
- **A meeting's page.** The route loader seeds the meeting's resource, so the page needs no second read; while the
  meeting is live or its notes are being written, the page polls and its notices change on their own: live, writing,
  failed with the run's reason (`notesNote.notices.failed.*`), or updated with the recording's speakers (MT-D3).
- **Voices.** A line's speaker is a voice index: the owner's voice reads "You" on one's own meeting and "Organizer"
  on another's, the others "Speaker N", a line with no voice "Unknown speaker" (`domain/meeting-page.ts`, `voiceOf`).
  On a live meeting without diarization voice 0 is the owner's.
- **Action items** are read-only (MT-D4) until the tasks slice owns them.
- **Rewrites.** A rewrite waits for its run up to 20 minutes; the page shows Leo writing and a toast when the notes
  are back or the run failed.
