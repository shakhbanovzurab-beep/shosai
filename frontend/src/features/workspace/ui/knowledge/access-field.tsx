"use client";

import { useTranslations } from "next-intl";

import { Field } from "@/components/ui/field";
import { FieldDescription, FieldLabel } from "@/components/ui/field-text";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { useWorkspace } from "../../model/use-workspace";
import { ProjectSelect } from "../meetings/project-select";
import { accessChoices } from "./knowledge-words";

/** Who in the current workspace Leo may answer from it for: everyone, or one of the member's teams. */
export function AccessField({ id, value, onChange }: { id: string; value: string; onChange: (key: string) => void }) {
  const { state, can } = useWorkspace();
  const t = useTranslations("workspaceKnowledge");
  return (
    <Field>
      <FieldLabel htmlFor={id}>{t("access.label")}</FieldLabel>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {accessChoices(t, state.teams, state.workspace.name, can.me, can.admin).map((option) => (
              <SelectItem key={option.key} value={option.key}>
                <span dir="auto">{option.label}</span>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <FieldDescription>{t("access.hint")}</FieldDescription>
    </Field>
  );
}

/** The project it belongs to in the current workspace; hidden while there are no open projects. */
export function KnowledgeProjectField({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string | null;
  onChange: (projectId: string | null) => void;
}) {
  const { state } = useWorkspace();
  return <ProjectSelect id={id} projects={state.projects} value={value} onChange={onChange} />;
}
