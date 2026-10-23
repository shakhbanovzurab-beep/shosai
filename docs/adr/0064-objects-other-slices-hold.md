# ADR 0064 — Objects other slices hold: task attachments in files

- **Status:** proposed on 2026-10-22 by the agent building tasks' step 3c, under the owner's instruction of the same day to carry the tasks slice through on its own and decide unusual points by industry practice; for the owner's review. Within FL-D4, FL-D6, FL-D9, ADR 0055 and inv-11, which it applies and does not change.
- **Packages:** `files` (step 8c), `tasks` (step 3c).
- **Context documents:** [files plan](../plan/slices/files.md) §3.2 ("Required by tasks"), FL-D4, FL-D6, FL-D9; [tasks plan](../plan/slices/tasks.md) §3.3, §3.13, KG-D3; [ADR 0055](0055-object-key-layout-and-bucket-rules.md); [ADR 0060](0060-kanban-golden-core.md); target architecture inv-11.

## Context

The Kanban golden core gives a task attachments: an upload for the task, or a copy of a File Manager file that shares its object (FL-D4), counted in the task owner's storage (KG-D3, FL-D6). Files' contract had only `Uploads.claim` and `FileReader`. A claimed upload of another slice lands under `transient/`, which the bucket expires after three days, and the storage port has no server-side copy. An object was deleted when no `storage_files` row named its key, so a purged File Manager file would have taken the object of an attachment copied from it. inv-11's reconciliation compared each person's counter with their files only, and its orphan scan would have reported any object another slice keeps under the person's prefix.

## Decision

1. **Files keeps every byte, the holding slice keeps its row.** A new files table `held_objects` (company isolation, like `storage_files`) is an object another slice holds: the key in its owner's prefix (`u/{user_id}/h/{id}`), its preview's key, name, type, size, the upload it came from and its holder (`task_attachment`). Tasks' `task_attachments` row names it by id.
2. **An object goes with its last holder.** `files_keys_in_use` answers for file rows and held objects, their previews too, so the purge, the erasure, a released held object and inv-11's orphan scan delete or report an object only when no row of either kind names it. A copy locks its source file's row, so a purge cannot pass between the read and the hold.
3. **Held bytes are the owner's storage.** A held object's bytes are in its owner's `used_bytes`: a `task_attachment` upload reserves like a File Manager upload and settles when held; a copy is charged like a File Manager copy. inv-11's reconciliation sums files and held objects. Held objects go with the person's data: exported with their bytes, copied to the other home, erased.
4. **The contract** is `HeldObjects` (`files.held_objects`): `limit`, `from_upload`, `from_file`, `release`, `discard`, `links`, `previews` and `prepare`, each in the caller's transaction or after its commit as the files plan §3.2 states.
5. **Previews are files' job.** `files.make_preview` makes a WebP at most 640 px wide of an image held object on the bulk queue with Pillow (13.0.0, the latest stable on 2026-10-22), decoding at most 40 megapixels; a failure leaves no preview, and the upload sweep queues an image left without one again.
6. **A holder releases what it no longer holds, on every path.** Tasks names the held object of every deleted attachment in `task_attachment_releases` by a trigger in the same transaction, so a cascade from a task, a board, an account or a workspace is covered; it releases them after its own deletions commit and in a tick every 15 minutes.
7. **Workspace storage waits for FL-D6.** Until files' step 8b opens a workspace's storage, an upload with `workspace_id` and an attachment on a workspace task answer 403 `storage_not_included`, and moving an attachment's bytes with its task into a workspace comes with 8b.

## Consequences

- A File Manager file and an attachment can share one object without either deleting it under the other.
- inv-11 covers attachments: a drifted counter or an orphaned held object is reported like a file's.
- Tasks never touches keys, quota or the bucket; another slice that needs to hold objects later takes the same contract with its own holder name.
- Pillow joins the backend's dependencies; image decoding runs only in workers, capped.
- Attachments on workspace tasks are unavailable until workspace storage exists.
