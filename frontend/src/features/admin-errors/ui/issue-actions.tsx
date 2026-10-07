"use client";

import Link from "next/link";

import { ClipboardCopy, LifeBuoy } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { copyText } from "@/lib/copy-text";

import type { IssueDetail } from "../domain/contract";
import { developerSummary } from "../domain/developer-summary";
import { ISSUE_STATUSES, type IssueStatus } from "../domain/dimensions";
import { updateIssue } from "../model/errors-store";
import { STATUS_ICON } from "./status-icons";

const UNASSIGNED = "none";

export function IssueActions({ issue }: { issue: IssueDetail }) {
  async function copySummary() {
    try {
      await copyText(developerSummary(issue, window.location.href));
      toast.success("Сводка скопирована", {
        description: "Markdown со стеком и контекстом — можно вставлять в задачу.",
      });
    } catch {
      toast.error("Не удалось скопировать");
    }
  }

  function change(patch: { status?: IssueStatus; assignee?: string | null }, done: string) {
    updateIssue(issue.id, patch).then(
      () => toast.success(done),
      () => undefined,
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select
        value={issue.status}
        onValueChange={(status) =>
          change(
            { status: status as IssueStatus },
            `Статус: ${ISSUE_STATUSES.find((s) => s.id === status)?.label ?? status}`,
          )
        }
      >
        <SelectTrigger size="sm" aria-label="Статус">
          <span className="text-muted-foreground">Статус:</span>
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper" align="start">
          <SelectGroup>
            {ISSUE_STATUSES.map((status) => {
              const Icon = STATUS_ICON[status.id];
              return (
                <SelectItem key={status.id} value={status.id}>
                  <Icon aria-hidden="true" />
                  {status.label}
                </SelectItem>
              );
            })}
          </SelectGroup>
        </SelectContent>
      </Select>

      <Select
        value={issue.assignee?.id ?? UNASSIGNED}
        onValueChange={(value) => {
          const assignee = value === UNASSIGNED ? null : value;
          const name = issue.assignees.find((candidate) => candidate.id === assignee)?.name;
          change({ assignee }, name ? `Назначено: ${name}` : "Исполнитель снят");
        }}
      >
        <SelectTrigger size="sm" aria-label="Исполнитель">
          <span className="text-muted-foreground">Исполнитель:</span>
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper" align="start">
          <SelectGroup>
            <SelectItem value={UNASSIGNED}>Не назначен</SelectItem>
            {issue.assignees.map((assignee) => (
              <SelectItem key={assignee.id} value={assignee.id}>
                {assignee.name}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>

      <Button variant="outline" size="sm" onClick={() => void copySummary()}>
        <ClipboardCopy aria-hidden="true" />
        Скопировать для разработчика
      </Button>

      {issue.support_ticket ? (
        <Button variant="outline" size="sm" asChild>
          <Link href={`/admin/support?ticket=${encodeURIComponent(issue.support_ticket.id)}`}>
            <LifeBuoy aria-hidden="true" />
            Обращение #{issue.support_ticket.number}
          </Link>
        </Button>
      ) : null}
    </div>
  );
}
