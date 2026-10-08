import { BookOpen, Gavel, type LucideIcon, Video } from "lucide-react";
import { useTranslations } from "use-intl";

import { Link } from "@/lib/navigation";

import { TeamPage } from "../shared/layout";
import { CreateWorkspaceForm } from "./create-workspace-form";

// What a workspace adds, worded in `create.value.<id>`.
const VALUE: { id: "meetings" | "work" | "knowledge"; icon: LucideIcon }[] = [
  { id: "meetings", icon: Video },
  { id: "work", icon: Gavel },
  { id: "knowledge", icon: BookOpen },
];

/** The "new workspace" page: what a workspace adds, and the form to start one. */
export function CreateWorkspace() {
  const t = useTranslations("workspace");
  return (
    <TeamPage className="max-w-4xl pt-2 md:pt-8">
      <div className="grid items-start gap-10 md:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <h1 className="text-balance font-semibold text-2xl tracking-tight sm:text-3xl">{t("create.title")}</h1>
            <p className="text-pretty text-muted-foreground">{t("create.intro")}</p>
          </div>
          <ul className="flex flex-col gap-5">
            {VALUE.map(({ id, icon: Icon }) => (
              <li key={id} className="flex gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg border bg-muted">
                  <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
                </span>
                <div className="flex flex-col gap-0.5">
                  <span className="font-medium text-sm">{t(`create.value.${id}.title`)}</span>
                  <span className="text-muted-foreground text-sm">{t(`create.value.${id}.text`)}</span>
                </div>
              </li>
            ))}
          </ul>
          <p className="text-muted-foreground text-sm">
            {t.rich("create.billing", {
              link: (chunks) => (
                <Link href="/app/upgrade" className="font-medium text-foreground underline-offset-4 hover:underline">
                  {chunks}
                </Link>
              ),
            })}
          </p>
        </div>
        <CreateWorkspaceForm />
      </div>
    </TeamPage>
  );
}
