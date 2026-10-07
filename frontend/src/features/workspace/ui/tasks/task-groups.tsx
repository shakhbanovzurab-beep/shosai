"use client";

import { useState } from "react";

import { ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

import type { Task } from "../../domain/content-contract";
import { groupTasks } from "../../domain/tasks";
import { TeamSection } from "../shared/layout";
import { TaskRow, type TaskRowContext } from "./task-row";

type ListProps = TaskRowContext & {
  items: Task[];
  showOwner: boolean;
  hideSource?: "meeting" | "project";
};

/** A card of rows; the list semantics carry the count for screen readers. */
export function TaskList({ items, ...rest }: ListProps) {
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {items.map((task) => (
        <TaskRow key={task.id} task={task} {...rest} />
      ))}
    </ul>
  );
}

/** Open tasks under Overdue, Due today, This week, Later and No due date; done ones folded away. */
export function TaskGroups(props: ListProps) {
  const { groups, done } = groupTasks(props.items, props.now);
  const [showDone, setShowDone] = useState(false);
  const t = useTranslations("workspaceTasks");

  return (
    <div className="flex flex-col gap-8">
      {groups.map((group) => (
        <TeamSection
          key={group.key}
          id={`due-${group.key}`}
          title={t(`groups.${group.key}`, { count: group.items.length })}
        >
          <TaskList {...props} items={group.items} />
        </TeamSection>
      ))}
      {done.length > 0 ? (
        <Collapsible open={showDone} onOpenChange={setShowDone} className="flex flex-col gap-3">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-fit text-muted-foreground">
              <ChevronRight
                data-icon="inline-start"
                className="transition-transform duration-200 motion-reduce:transition-none rtl:-scale-x-100 ltr:[[data-state=open]_&]:rotate-90 rtl:[[data-state=open]_&]:-rotate-90"
              />
              {showDone ? t("hideDone") : t("showDone", { count: done.length })}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <TaskList {...props} items={done} />
          </CollapsibleContent>
        </Collapsible>
      ) : null}
    </div>
  );
}
