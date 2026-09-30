# F2 — Frontend foundation

Follow the common protocol in `docs/plan/prompts/README.md`. Load the skills `vercel-react-best-practices`, `vercel-composition-patterns`, `vercel-react-view-transitions` and `web-design-guidelines` before writing code.

## Goal

A frontend project in `frontend/` that looks exactly like the draft's shell — navigation, layout, typography, colours, theme, loading and error states — and that every slice builds its screens into. After this package the frontend CI job runs and is green.

## Read first

- CLAUDE.md "Frontend" and "Checks"; target architecture §4.2 (web cabinet), §18.2 (frontend libraries and versions).
- The draft: `/root/whisperer/frontend/src/app/` (shell, router manifest), `src/shared/`, styles, Tailwind configuration, fonts, icons, `src/locales/`, `index.html`, `vite.config.ts`, `public/`.
- `parity/README.md` from D2.

## Work

1. Vite project with React 19.3, TypeScript, and the libraries and versions from target architecture §18.2, pinned in `package-lock.json`; `.nvmrc` with Node.js 26.10.0.
2. npm scripts required by CLAUDE.md "CI": `typecheck`, `test` (single run), `build`, `doctor` (react-doctor pinned in `package.json`).
3. Carry over the draft's visual foundation so screens can match pixel for pixel: design tokens, Tailwind theme, fonts, icons, global styles, the app shell and navigation. Rewrite the code to the v2 rules (feature-first slices, file length ≤ 200 lines, no barrel files); keep the look identical.
4. Router with lazy-loaded routes per feature, and a registration point where each slice adds its routes and navigation entries.
5. Data fetching layer against the v2 API contract, with the error envelope from F1 and `request_id` shown to the user on errors.
6. i18n with all 16 locales. Carry over the draft's translation files; keep keys stable so slices can bring their screens' texts.
7. Wire the D2 parity harness to this project.

## Definition of done

- `npm run doctor -- --score` prints 100; `typecheck`, `test` and `build` pass.
- The parity harness shows no difference between the draft and v2 for the shell: navigation, empty layout, not-found page, in both themes and on both viewports.
- CI frontend job is green after push.
