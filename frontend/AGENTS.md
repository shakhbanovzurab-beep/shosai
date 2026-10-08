# AGENTS.md

## Project overview

The Whisperer cabinet: a Vite single-page app with React 19, TypeScript, React Router, TanStack Query,
`use-intl`, Tailwind CSS v4 and shadcn/ui. See `README.md` and `docs/architecture.md`.

This repository uses the shadcn `radix-nova` style. The shadcn CLI reports `base: "radix"`, which refers to Radix UI. Always inspect the local components in `src/components/ui/` because individual wrappers may use different primitives.

## shadcn skill

Use the shadcn skill for all work involving shadcn/ui components, styling, composition, registries, presets, or `components.json`.

If the skill is not available, install it with:

```bash
npx skills add shadcn/ui
```

The skill contains the component, styling, composition, accessibility, and CLI rules. Do not duplicate those rules here. Always inspect the local component source before using it.

Keep the components inside `src/components/ui/` and `src/components/calendar/` as vendored: apply styling or customization where they are used. They follow the 200-line limit, so a long component is split into files by part (`sidebar.tsx`, `sidebar-menu.tsx`, …), imported by direct path.

## Setup

This project uses npm.

```bash
npm ci
npm run dev
```

Available commands: `npm run dev`, `dev:api`, `build`, `preview`, `typecheck`, `test`, `doctor`, `api:types`,
`check`, `check:fix`, `i18n:check`, `i18n:rtl-smoke`, `generate:presets`. `npm test` runs the unit tests and the
architecture, i18n and API-types checks.

## Feature-sliced structure

The architecture is described in `docs/architecture.md`; `src/scripts/architecture.test.ts` enforces it.

- Business code lives in vertical slices: `src/features/<slice>/` with `domain/`, `data/`, `api/`, `model/`, `ui/`, `mocks/` layers as needed.
- No barrel files: there is no `index.ts`; import the module that defines a symbol by its path.
- `src/app/` holds routing only: route tables (`routes/`), layouts, page modules (`pages/`) and error pages.
- User panel pages (URL `/app/<screen>`): `src/app/pages/user/<screen>.tsx`; admin pages (URL `/admin/<screen>`): `src/app/pages/admin/<screen>.tsx`, backed by `admin-<screen>` slices. Register each in `src/app/routes/`.
- Shared, business-agnostic code: `src/components/` (with shadcn in `src/components/ui/`), `src/hooks/`, `src/lib/`.
- Theme presets: `src/styles/presets/`

Keep code inside its slice until another slice needs it; then import it from the owning slice by path, or move it to the shared layer only if it carries no business knowledge.

## Creating or extending a screen

1. Inspect the closest current slice before writing code. Studio, Knowledge base, and the admin Plans and Billing slices are useful references.
2. When reproducing a UI from a screenshot or image, follow its visual direction closely, including layout, hierarchy, spacing, component structure, and important details. Implement it with the project's existing components and semantic theme tokens rather than copying raw color values. If the design needs a color that is not available through the existing theme tokens, or the user explicitly requests a non-theme color, use a named color from Tailwind's default palette. Do not use arbitrary hex, RGB, HSL, or OKLCH values.
3. Reuse the existing dashboard shell, local components, layout controls, and theme tokens.
4. Build the screen as a slice in `src/features/<slice>/`, split into focused components in its `ui/` layer. Keep the page module small: `PageMeta`, query parsing and the slice's screen.
5. Navigate only through `@/lib/navigation`; read data through the slice's `api/` (sample paths answered by `mocks/` until the backend has the endpoints).
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
- User panel (`/app`) text goes through the `use-intl` catalogs, never hardcoded: follow `docs/i18n.md` and `src/i18n/GLOSSARY.md`, and run `npm test`. The admin panel (`/admin`) is written in Russian only.
- Avoid unnecessary dependencies.
- Keep changes focused and do not refactor unrelated files.

## Contributions

- Use conventional commit prefixes such as `feat:`, `fix:`, `refactor:`, `docs:`, and `chore:`.
- Include screenshots for new screens and material visual changes. Include mobile and dark-theme states when relevant.
- Explain new reusable patterns or dependencies in the pull request.
- Follow `CONTRIBUTING.md` for the contribution workflow.
