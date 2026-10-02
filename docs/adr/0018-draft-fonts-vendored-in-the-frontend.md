# ADR 0018 — The draft's font files are vendored in the frontend

- **Status:** accepted by the owner on 2026-10-02 (F2 planning, decision F2-D2).
- **Package:** F2, frontend foundation; the public site (S17) serves the same files.
- **Context documents:** [F2 plan](../plan/packages/F2-frontend-foundation.md) §3.5; draft spec 084 (font roles); [parity/README.md](../../parity/README.md) "What v2 must keep"; [CLAUDE.md](../../.claude/CLAUDE.md) "Rewrite from the draft".

## Context

- Users must notice no visual difference, and the parity harness compares pixels. Glyphs depend on the exact font file: another version or another subset of the same family can move text by a pixel.
- The draft keeps its fonts in git and serves them at `/fonts/`:
  - `backend/static/webfonts`: 1 603 woff2 slices and 80 generated `roles-<lang>-<role>.css` stylesheets (16 languages × 5 roles), 61 MB;
  - `backend/static/landing/fonts`: 42 built woff2 files, 1.1 MB.
- Alternatives considered:
  - `@fontsource/*` packages pinned in the lock file: no binaries in git, but other files and subsets than the draft's, and not every family the draft uses (Pretendard, D2Coding, Kawkab Mono) is published there;
  - downloading the files at build time from the bucket: the build would depend on the network and on secrets.

## Decision

1. `frontend/fonts/` holds byte-identical copies of the draft's woff2 files that the stylesheets reference, and the role stylesheets regenerated from the font catalogue by the carried-over generator (`@generated`). The build copies the directory to `dist/fonts/`; it is served at `/fonts/`.
2. A test resolves every `url()` of every stylesheet to a vendored file, and the generator's `--check` mode fails on drift; both run in `npm test`.
3. The files change only through a deliberate font change, never by a dependency upgrade.

## Consequences

- Up to 62 MB of binaries enter git history once. A clone and a CI checkout grow by that size; CI caches only npm.
- The font catalogue stays the one source of the role mapping (spec 084); the pre-paint script in `index.html` is kept equal to it by a test.
- S17 serves the same directory, so the public site and the cabinet use the same files.

## Revisit when

- The repository size slows clones or CI noticeably: move the directory to Git LFS with the same paths.
- A font family is replaced or updated: re-baseline the affected parity states.
