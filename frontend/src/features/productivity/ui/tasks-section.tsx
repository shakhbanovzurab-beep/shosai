"use client";

import { useState } from "react";

import { cn } from "cn";
import { Plus } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { NameDialog, type NameRequest } from "@/components/name-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { MyWorkspaceTasks } from "@/features/workspace/ui/personal/my-workspace-tasks";
import { CALENDAR_DAY } from "@/i18n/calendar-days";

import { type Task, tasks } from "../data/tasks";

/** A time of day ("14:00") in the interface language: "2:00 PM", "14:00". */
function TaskTime({ time }: { time: string }) {
  const format = useFormatter();
  // Время суток, а не момент: оно стоит на дне UTC и печатается в UTC, поэтому везде читается как записано.
  return <time dateTime={time}>{format.dateTime(new Date(`1970-01-01T${time}:00Z`), "time", CALENDAR_DAY)}</time>;
}

function TaskRow({ task, onToggle }: { task: Task; onToggle: (checked: boolean) => void }) {
  const id = `task-${task.id}`;
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <Checkbox id={id} checked={task.checked} onCheckedChange={(checked) => onToggle(checked === true)} />
      <label
        htmlFor={id}
        className={cn("min-w-0 flex-1 truncate text-sm", task.checked && "text-muted-foreground line-through")}
      >
        <span dir="auto">{task.title}</span>
      </label>
      {task.tag ? (
        <Badge variant="outline" dir="auto" className="hidden font-normal sm:inline-flex">
          {task.tag}
        </Badge>
      ) : null}
      {task.time ? (
        <span className="min-w-16 shrink-0 text-end text-muted-foreground text-sm tabular-nums">
          <TaskTime time={task.time} />
        </span>
      ) : null}
    </li>
  );
}

/** The day's tasks: your own list, then what your workspaces assigned to you (live, not copies). */
export function TasksSection() {
  const t = useTranslations("productivity");
  const [items, setItems] = useState(tasks);
  const [request, setRequest] = useState<NameRequest | null>(null);
  const done = items.filter((task) => task.checked).length;

  const addTask = () =>
    setRequest({
      title: t("tasks.newTask"),
      initial: "",
      submitLabel: t("tasks.addTask"),
      onSubmit: (title) =>
        setItems((current) => [...current, { id: crypto.randomUUID(), title, tag: null, time: null, checked: false }]),
    });

  return (
    <section aria-labelledby="tasks-today" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-4">
          <h2 id="tasks-today" className="flex items-baseline gap-2 text-xl tracking-tight">
            {t("tasks.heading")}
            <span className="text-muted-foreground text-sm tabular-nums">
              {t("tasks.progress", { done, total: items.length })}
            </span>
          </h2>
          <Button variant="outline" size="sm" onClick={addTask}>
            <Plus data-icon="inline-start" />
            {t("tasks.newTask")}
          </Button>
        </div>
        <ul className="divide-y overflow-hidden rounded-xl border bg-background shadow-xs">
          {items.map((task) => (
            <TaskRow
              key={task.id}
              task={task}
              onToggle={(checked) =>
                setItems((current) => current.map((item) => (item.id === task.id ? { ...item, checked } : item)))
              }
            />
          ))}
        </ul>
      </div>
      <MyWorkspaceTasks />
      <NameDialog request={request} onClose={() => setRequest(null)} />
    </section>
  );
}
