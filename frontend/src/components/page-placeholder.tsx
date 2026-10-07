import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

interface PagePlaceholderProps {
  readonly title: string;
  readonly description: string;
  readonly icon: LucideIcon;
}

/** The "on the way" block on its own, for pages that don't want the heading above it. */
export function PlaceholderState({ title, icon: Icon }: Pick<PagePlaceholderProps, "title" | "icon">) {
  const t = useTranslations("pages");
  return (
    <Empty className="min-h-96 border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle>{t("placeholder.title", { title })}</EmptyTitle>
        <EmptyDescription>{t("placeholder.description")}</EmptyDescription>
      </EmptyHeader>
      <Badge variant="secondary">{t("placeholder.badge")}</Badge>
    </Empty>
  );
}

export function PagePlaceholder({ title, description, icon }: PagePlaceholderProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl leading-none tracking-tight">{title}</h1>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>
      <PlaceholderState title={title} icon={icon} />
    </div>
  );
}
