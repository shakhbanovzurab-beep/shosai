"use client";

import type { ReactNode } from "react";

import { Check, ChevronsUpDown, RotateCw } from "lucide-react";
import { useTranslations } from "use-intl";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";
import { SidebarMenuButton } from "@/components/ui/sidebar-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/lib/navigation";

import type { WorkspaceSummary } from "../../domain/contract";
import { workspacePath } from "../../domain/paths";
import { useWorkspaces, workspacesResource } from "../../model/resources";
import { SwitcherActions } from "./switcher-actions";
import { PersonalTile, WorkspaceTile } from "./workspace-tile";

function ScopeOption({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) {
  const t = useTranslations("workspace");
  return (
    <DropdownMenuItem asChild>
      <Link href={href} aria-current={active ? "page" : undefined} className="gap-2.5 py-2">
        {children}
        {active ? <Check className="ms-auto" aria-label={t("switcher.current")} /> : null}
      </Link>
    </DropdownMenuItem>
  );
}

const OptionText = ({ title, detail }: { title: string; detail: string }) => (
  <span className="flex min-w-0 flex-col">
    <span dir="auto" className="truncate font-medium">
      {title}
    </span>
    <span className="truncate text-muted-foreground text-xs">{detail}</span>
  </span>
);

function TriggerLabel({
  current,
  loading,
  brand,
}: {
  current: WorkspaceSummary | null;
  loading: boolean;
  brand: ReactNode;
}) {
  if (current)
    return (
      <>
        <WorkspaceTile name={current.name} />
        <span dir="auto" className="truncate font-semibold text-base">
          {current.name}
        </span>
      </>
    );
  if (loading)
    return (
      <>
        <Skeleton className="size-5 rounded-md" />
        <Skeleton className="h-4 w-24" />
      </>
    );
  return (
    <>
      <PersonalTile />
      {brand}
    </>
  );
}

/**
 * Personal or one of the account's workspaces, top left as in every team product. The current
 * context is always visible; every other one is a single choice away, and so is starting a new one.
 * `brand` — название приложения рядом с логотипом в личном пространстве; его начертание задаёт оболочка.
 */
export function WorkspaceSwitcher({ slug, brand }: { slug: string | null; brand: ReactNode }) {
  const t = useTranslations("workspace");
  const workspaces = useWorkspaces();
  const list = workspaces.status === "ready" ? workspaces.data.workspaces : [];
  const current = slug ? (list.find((w) => w.slug === slug) ?? null) : null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton className="min-w-0 flex-1 data-[state=open]:bg-sidebar-accent">
          <TriggerLabel current={current} loading={slug !== null && workspaces.status === "loading"} brand={brand} />
          <span className="sr-only">{t("switcher.hint")}</span>
          <ChevronsUpDown className="ms-auto text-sidebar-foreground/60" aria-hidden="true" />
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" sideOffset={6} className="w-(--radix-dropdown-menu-trigger-width) min-w-64">
        <DropdownMenuGroup>
          <ScopeOption href="/app/productivity" active={slug === null}>
            <span className="grid size-7 shrink-0 place-items-center rounded-md border">
              <PersonalTile className="size-4!" />
            </span>
            <OptionText title={t("switcher.personal")} detail={t("switcher.personalHint")} />
          </ScopeOption>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-muted-foreground text-xs">{t("switcher.workspaces")}</DropdownMenuLabel>
        <DropdownMenuGroup>
          {list.map((workspace) => (
            <ScopeOption key={workspace.id} href={workspacePath(workspace.slug)} active={workspace.slug === slug}>
              <WorkspaceTile name={workspace.name} className="size-7 text-xs" />
              <OptionText
                title={workspace.name}
                detail={
                  workspace.suspended
                    ? t("switcher.suspended")
                    : t("switcher.detail", {
                        role: t(`roles.${workspace.role}.label`),
                        count: workspace.member_count,
                      })
                }
              />
            </ScopeOption>
          ))}
          {workspaces.status === "loading" ? (
            <DropdownMenuItem disabled className="gap-2.5 py-2">
              <Skeleton className="size-7 rounded-md" />
              <Skeleton className="h-4 w-28" />
            </DropdownMenuItem>
          ) : null}
          {workspaces.status === "error" ? (
            <DropdownMenuItem onSelect={() => void workspacesResource.refresh()}>
              <RotateCw />
              {t("switcher.loadFailed")}
            </DropdownMenuItem>
          ) : null}
          {workspaces.status === "ready" && list.length === 0 ? (
            <DropdownMenuItem disabled className="text-muted-foreground text-xs">
              {t("switcher.none")}
            </DropdownMenuItem>
          ) : null}
        </DropdownMenuGroup>
        <SwitcherActions current={current} />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
