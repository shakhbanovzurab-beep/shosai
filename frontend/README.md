# Next.js Admin Template with TypeScript & Shadcn UI

**Studio Admin** - Includes multiple dashboards, authentication layouts, customizable theme presets, and more.

Most admin templates I found, free or paid, felt cluttered, outdated, or too rigid. I built this as a cleaner alternative with features often missing in others, such as theme toggling and layout controls, while keeping the design modern, minimal, and flexible.

## Features

- Built with Next.js 16, TypeScript, Tailwind CSS v4, and Shadcn UI  
- Responsive and mobile-friendly  
- Customizable theme presets (light/dark modes with color schemes like Tangerine, Brutalist, and more)  
- Flexible layouts (collapsible sidebar, variable content widths)  
- Authentication flows and screens  
- Prebuilt dashboards (Default, CRM, Finance, Analytics, Productivity) plus legacy variants  
- Role-Based Access Control (RBAC) with config-driven UI and multi-tenant support *(planned)*  

> [!NOTE]
> The default dashboard uses the **shadcn neutral** theme.  
> It also includes additional color presets inspired by [Tweakcn](https://tweakcn.com):  
>
> - Tangerine  
> - Neo Brutalism  
> - Soft Pop  
>
> You can create more presets by following the same structure as the existing ones.

## Tech Stack

- **Framework**: Next.js 16 (App Router), TypeScript, Tailwind CSS v4  
- **UI Components**: Shadcn UI  
- **Validation**: Zod  
- **Forms & State Management**: React Hook Form, Zustand  
- **Tables & Data Handling**: TanStack Table  
- **Tooling & DX**: Biome, Husky  

## Screens

### Available
- Default Dashboard  
- CRM Dashboard  
- Finance Dashboard  
- Analytics Dashboard  
- Productivity Dashboard  
- E-commerce Dashboard  
- Academy Dashboard  
- Logistics Dashboard  
- Infrastructure Dashboard  
- File Manager  
- Patient Monitoring  
- Chat Page  
- Email Page  
- Profile  
- Users Management  
- Roles Management  
- Kanban Board  
- Tasks Page  
- Invoice Page  
- Calendar Page  
- Authentication (4 screens)  
- Legacy: Default v1, CRM v1, Finance v1, Analytics v1

### Planned
I’ve added all the planned screens. Feel free to open an issue for requesting something specific.

## Feature-Sliced Architecture

Business code is organised by capability, not by technical layer: each feature is a vertical slice in
`src/features/<slice>/` with its own domain logic, data access, state, UI and route handlers, layered by
Clean Architecture rules. `src/app/` only routes to slices, and shared UI, hooks and utilities that know
nothing about the business live at the top level.

See [docs/architecture.md](docs/architecture.md) for the rules; `npm run lint:architecture` checks them.

## Getting Started

### Run locally

From the project root:

1. **Install dependencies**
   ```bash
    npm install
   ```

2. **Start the development server**
   ```bash
   npm run dev
   ```

Your app will be running at [http://localhost:3000](http://localhost:3000)

### Site address

Set `SITE_URL` to the site's public address, for example in `.env.production.local`:

```bash
SITE_URL=https://example.com
```

It is read at build time for the sitemap, the `Sitemap` line in robots.txt and absolute Open Graph image URLs.
Without it the sitemap is empty, robots.txt has no `Sitemap` line and Open Graph images point to `localhost`.

### Formatting and Linting

Format, lint, and organize imports
```bash
npx @biomejs/biome check --write
```
> For more information on available rules, fixes, and CLI options, refer to the [Biome documentation](https://biomejs.dev/).

---

> [!IMPORTANT]  
> This project is updated frequently. If you’re working from a fork or an older clone, pull the latest changes before syncing. Some updates may include breaking changes.

---

Contributions are welcome. Feel free to open issues, feature requests, or start a discussion.


**Happy Vibe Coding!**
