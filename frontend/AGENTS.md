# AGENTS.md

## Project overview

Studio Admin is a responsive admin dashboard built with Next.js 16, React 19, TypeScript, Tailwind CSS v4, and shadcn/ui.

This repository uses the shadcn `radix-nova` style. The shadcn CLI reports `base: "radix"`, which refers to Radix UI. Always inspect the local components in `src/components/ui/` because individual wrappers may use different primitives.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## shadcn skill

Use the shadcn skill for all work involving shadcn/ui components, styling, composition, registries, presets, or `components.json`.

If the skill is not available, install it with:

```bash
npx skills add shadcn/ui
```

The skill contains the component, styling, composition, accessibility, and CLI rules. Do not duplicate those rules here. Always inspect the local component source before using it.

Do not modify files inside `src/components/ui/` or `src/components/calendar/`. Keep these components intact and apply styling or customization where they are used.

## Setup

This project uses npm.

```bash
npm install
npm run dev
```

Available commands:

```bash
npm run build
npm run lint
npm run format
npm run check
npm run check:fix
npm run lint:architecture
npm run typecheck
npm run i18n:check
npm run i18n:rtl-smoke -- --base http://localhost:3000
npm run generate:presets
npm test
```

`npm test` runs the unit tests (`src/**/*.test.ts`, Node's built-in test runner) for pure domain code. Run build, lint, check, tests or other validation commands only when the user explicitly requests that validation.

## Feature-sliced structure

The architecture is described in `docs/architecture.md`; `npm run lint:architecture` enforces it.

- Business code lives in vertical slices: `src/features/<slice>/` with `domain/`, `data/`, `api/`, `model/`, `ui/`, `server/` layers as needed.
- A slice is used from outside only through `@/features/<slice>` (`index.ts`, client-safe) or `@/features/<slice>/server` (`server.ts`).
- `src/app/` holds routing only: pages, layouts and route handlers that render or re-export a slice's public API.
- User panel routes (URL `/app/<screen>`): `src/app/(main)/app/(panel)/<screen>/page.tsx`; admin routes (URL `/admin/<screen>`): `src/app/(main)/admin/<screen>/page.tsx`, backed by `admin-<screen>` slices.
- Shared, business-agnostic code: `src/components/` (with shadcn in `src/components/ui/`), `src/hooks/`, `src/lib/`, `src/server/`.
- Theme presets: `src/styles/presets/`

Keep code inside its slice until another slice needs it; then expose it through the owning slice's public API, or move it to the shared layer only if it carries no business knowledge.

## Creating or extending a screen

1. Inspect the closest current slice before writing code. Studio, Knowledge base, and the admin Plans and Billing slices are useful references.
2. When reproducing a UI from a screenshot or image, follow its visual direction closely, including layout, hierarchy, spacing, component structure, and important details. Implement it with the project's existing components and semantic theme tokens rather than copying raw color values. If the design needs a color that is not available through the existing theme tokens, or the user explicitly requests a non-theme color, use a named color from Tailwind's default palette. Do not use arbitrary hex, RGB, HSL, or OKLCH values.
3. Reuse the existing dashboard shell, local components, layout controls, and theme tokens.
4. Build the screen as a slice in `src/features/<slice>/`, split into focused components in its `ui/` layer. Keep `page.tsx` small: metadata, `searchParams` parsing and the slice's screen.
5. Keep `page.tsx` as a Server Component by default. Move interactive or browser-dependent code into a dedicated Client Component.
6. Add the screen to the navigation config in the `shell` slice when it should appear in the sidebar.
7. Decide the information hierarchy before choosing widgets. Let the content determine the page structure.
8. Keep the established visual rhythm where it fits: compact spacing, clear typography hierarchy, responsive action rows, and grids that collapse cleanly on smaller screens.
9. Widget selection is not a fixed formula. Try different arrangements of cards, resource rows, meters, charts, tabs, empty states, and actions, then keep the version that communicates the content clearly and feels consistent with the project.
10. Match nearby screens in card density, borders, radius, spacing, content width, and responsive behavior.
11. Use semantic theme tokens so new screens work with light mode, dark mode, and the existing theme presets.
12. Handle relevant loading, empty, error, disabled, and overflow states.
13. Keep screens accessible with semantic HTML, keyboard support, visible focus states, labels, and appropriate ARIA attributes.

## Code conventions

- TypeScript strict mode is enabled. Use precise types and avoid `any`.
- Use the existing `@/` import aliases.
- Follow the Biome configuration: double quotes, semicolons, two-space indentation, sorted imports, and a 120-character line width.
- User panel (`/app`) text goes through the `next-intl` catalogs, never hardcoded: follow `docs/i18n.md` and `src/i18n/GLOSSARY.md`, and run `npm run i18n:check`. The admin panel (`/admin`) is written in Russian only.
- Avoid unnecessary dependencies.
- Keep changes focused and do not refactor unrelated files.

## Contributions

- Use conventional commit prefixes such as `feat:`, `fix:`, `refactor:`, `docs:`, and `chore:`.
- Include screenshots for new screens and material visual changes. Include mobile and dark-theme states when relevant.
- Explain new reusable patterns or dependencies in the pull request.
- Follow `CONTRIBUTING.md` for the contribution workflow.
