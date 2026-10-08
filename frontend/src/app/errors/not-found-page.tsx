import { CalendarDays, Command, Home, KanbanSquare, LifeBuoy, Mail } from "lucide-react";
import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { Button } from "@/components/ui/button";
import { APP_CONFIG } from "@/config/app-config";
import { Link } from "@/lib/navigation";

import { GoBackButton } from "./go-back-button";

const HOME = "/app/productivity";

// Section names come from the shell's navigation catalog, so they read as they do in the sidebar.
const SHORTCUTS = [
  { href: "/app/mail", key: "nav.email", icon: Mail },
  { href: "/app/calendar", key: "nav.calendar", icon: CalendarDays },
  { href: "/app/kanban", key: "nav.kanban", icon: KanbanSquare },
  { href: "/app/support", key: "userMenu.support", icon: LifeBuoy },
] as const;

/** The page for an address the cabinet doesn't have, or a thing that no longer exists. */
export function NotFoundPage() {
  const t = useTranslations("pages");
  const nav = useTranslations("shell");
  return (
    <main className="relative isolate flex min-h-dvh flex-col overflow-hidden bg-background">
      {/* Faint grid that fades out towards the edges, plus a soft glow behind the number. */}
      <div
        aria-hidden="true"
        className="mask-[radial-gradient(ellipse_at_center,black_20%,transparent_70%)] absolute inset-0 -z-10 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-size-[48px_48px] opacity-60"
      />
      <div
        aria-hidden="true"
        className="absolute top-1/3 left-1/2 -z-10 size-[32rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/10 blur-3xl"
      />

      <PageMeta title={t("notFound.metaTitle")} />
      <header className="flex items-center px-4 py-4 sm:px-8">
        <Link
          href={HOME}
          prefetch={false}
          className="flex items-center gap-2 rounded-md font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Command className="size-5" aria-hidden="true" />
          {APP_CONFIG.name}
        </Link>
      </header>

      <section className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center px-4 pb-24 text-center">
        <span className="rounded-full border bg-background/80 px-3 py-1 font-medium text-muted-foreground text-xs backdrop-blur">
          {t("notFound.badge", { code: "404" })}
        </span>
        <p
          aria-hidden="true"
          className="mt-6 select-none bg-linear-to-b from-foreground to-foreground/15 bg-clip-text font-semibold text-[7rem] text-transparent leading-none tracking-tighter sm:text-[10rem]"
        >
          404
        </p>
        <h1 className="mt-4 font-semibold text-2xl tracking-tight sm:text-3xl">{t("notFound.title")}</h1>
        <p className="mt-3 text-balance text-muted-foreground">{t("notFound.description")}</p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg">
            <Link href={HOME} prefetch={false}>
              <Home data-icon="inline-start" />
              {t("actions.goHome")}
            </Link>
          </Button>
          <GoBackButton fallbackHref={HOME} />
        </div>

        <nav aria-label={t("notFound.popularPages")} className="mt-12 w-full">
          <p className="text-muted-foreground text-xs">{t("notFound.jumpTo")}</p>
          <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {SHORTCUTS.map(({ href, key, icon: Icon }) => (
              <li key={href}>
                <Link
                  href={href}
                  prefetch={false}
                  className="flex items-center justify-center gap-2 rounded-lg border bg-card/60 px-3 py-2.5 text-sm backdrop-blur transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
                  {nav(key)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </section>
    </main>
  );
}
