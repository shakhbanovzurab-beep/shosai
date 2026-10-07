"use client";

import { useTranslations } from "next-intl";

import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import type { Project } from "../../domain/contract";

const NONE = "none";

/** Which project something belongs to, or none; hidden while the workspace has no projects. */
export function ProjectSelect({
  id,
  projects,
  value,
  onChange,
}: {
  id: string;
  projects: Project[];
  value: string | null;
  onChange: (projectId: string | null) => void;
}) {
  const t = useTranslations("workspaceMeetings.project");
  const open = projects.filter((p) => p.status !== "completed" || p.id === value);
  if (open.length === 0) return null;
  return (
    <div className="flex items-center justify-between gap-4">
      <Label htmlFor={id} className="font-medium text-sm">
        {t("label")}
      </Label>
      <Select value={value ?? NONE} onValueChange={(next) => onChange(next === NONE ? null : next)}>
        <SelectTrigger id={id} size="sm" className="w-44">
          <SelectValue />
        </SelectTrigger>
        <SelectContent align="end">
          <SelectGroup>
            <SelectItem value={NONE}>{t("none")}</SelectItem>
            {open.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                <span dir="auto">{p.name}</span>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}
