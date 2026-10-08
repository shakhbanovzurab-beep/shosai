import { useFormatter, useNow, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import { projects } from "../data/projects";
import { dayFromToday } from "../domain/days";

/** Active projects: status, how far along, and when each is due. */
export function ProjectsSection() {
  const t = useTranslations("productivity");
  const format = useFormatter();
  const now = useNow();

  return (
    <section aria-labelledby="projects" className="flex flex-col gap-2">
      <h2 id="projects" className="text-xl tracking-tight">
        {t("projects.heading")}
      </h2>
      <div className="grid gap-4 md:grid-cols-3">
        {projects.map((project) => {
          const due = dayFromToday(project.dueInDays, now.getTime());
          return (
            <Card key={project.id} className="shadow-xs">
              <CardHeader>
                <CardTitle>
                  <span dir="auto">{project.title}</span>
                </CardTitle>
                <CardAction>
                  <Badge variant="outline" className="font-normal">
                    {t(`projects.status.${project.status}`)}
                  </Badge>
                </CardAction>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                <div className="flex items-center gap-3">
                  {/* The shared bar fills from the left; mirrored, it fills from the start in right-to-left too. */}
                  <Progress
                    value={project.progress}
                    aria-label={t("projects.progressOf", { project: project.title })}
                  />
                  <span className="shrink-0 text-sm tabular-nums">
                    {format.number(project.progress / 100, "percent")}
                  </span>
                </div>
                <span className="text-muted-foreground text-sm">
                  {t("projects.due", { date: format.dateTime(due, "short") })}
                </span>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
