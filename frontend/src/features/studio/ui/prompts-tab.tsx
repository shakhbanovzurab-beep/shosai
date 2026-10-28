"use client";

import { useState } from "react";

import { Layers, MessageSquareText, Plus, Search } from "lucide-react";
import { useTranslations } from "use-intl";

import { ConfirmDestructive, LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";

import type { Prompt } from "../domain/contract";
import { ROLES } from "../domain/roles";
import { removePrompt } from "../model/prompt-actions";
import { promptsResource, usePrompts, useSkills } from "../model/studio-resources";
import { useProblemWords } from "../model/use-problem-words";
import { type EditorTarget, PromptEditorDialog } from "./prompt-editor-dialog";
import { type PromptRowActions, PromptsTable } from "./prompts-table";
import { RoleFilter, type RoleFilterValue } from "./role-filter";
import { SkillsDialog } from "./skills-dialog";
import { TabIntro } from "./tab-intro";

const draftOf = ({ name, role, content, skill_ids }: Prompt) => ({ name, role, content, skill_ids });

export function PromptsTab() {
  const t = useTranslations("studioPrompts");
  const tc = useTranslations("common");
  const words = useProblemWords();
  const state = usePrompts();
  const skillsState = useSkills();
  const skills = skillsState.status === "ready" ? skillsState.data.skills : [];
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<RoleFilterValue>("all");
  const [editor, setEditor] = useState<EditorTarget | null>(null);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [deleting, setDeleting] = useState<Prompt | null>(null);

  const create = () =>
    setEditor({
      mode: "create",
      draft: { name: "", role: role === "all" ? ROLES[0].id : role, content: "", skill_ids: [] },
    });
  const actions: PromptRowActions = {
    edit: (prompt) => setEditor({ mode: "edit", id: prompt.id, draft: draftOf(prompt) }),
    duplicate: (prompt) =>
      setEditor({ mode: "create", draft: { ...draftOf(prompt), name: t("copyName", { name: prompt.name }) } }),
    remove: setDeleting,
  };

  const needle = query.trim().toLowerCase();
  const all = state.status === "ready" ? state.data.prompts : [];
  const shown = all.filter((p) => (role === "all" || p.role === role) && p.name.toLowerCase().includes(needle));

  return (
    <div className="flex flex-col gap-6">
      <TabIntro>{t("intro")}</TabIntro>
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
        <InputGroup className="h-9 xl:max-w-80">
          <InputGroupAddon>
            <Search />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            dir="auto"
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            placeholder={t("search.placeholder")}
            aria-label={t("search.label")}
          />
        </InputGroup>
        <RoleFilter value={role} onChange={setRole} />
        <Button variant="outline" className="w-fit xl:ms-auto" onClick={() => setSkillsOpen(true)}>
          <Layers data-icon="inline-start" />
          {t("skills")}
        </Button>
      </div>
      {state.status === "loading" ? <Skeleton className="h-64 rounded-xl" /> : null}
      {state.status === "error" ? (
        <LoadError title={t("loadFailed")} message={state.message} onRetry={() => void promptsResource.refresh()} />
      ) : null}
      {state.status === "ready" && shown.length > 0 ? (
        <PromptsTable prompts={shown} data={state.data} skills={skills} actions={actions} />
      ) : null}
      {state.status === "ready" && shown.length === 0 ? (
        <Empty className="border border-dashed">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <MessageSquareText />
            </EmptyMedia>
            <EmptyTitle>{all.length === 0 ? t("empty.title") : t("noMatches.title")}</EmptyTitle>
            <EmptyDescription>
              {all.length === 0 ? t("empty.description") : t("noMatches.description")}
            </EmptyDescription>
          </EmptyHeader>
          {all.length === 0 ? (
            <EmptyContent>
              <Button size="sm" onClick={create}>
                <Plus data-icon="inline-start" />
                {tc("actions.create")}
              </Button>
            </EmptyContent>
          ) : null}
        </Empty>
      ) : null}

      <PromptEditorDialog target={editor} skills={skills} onClose={() => setEditor(null)} />
      <SkillsDialog open={skillsOpen} onClose={() => setSkillsOpen(false)} />
      <ConfirmDestructive
        open={deleting !== null}
        title={t("delete.title", { name: deleting?.name ?? "" })}
        description={t("delete.description")}
        confirmLabel={tc("actions.delete")}
        onConfirm={() => deleting && void removePrompt(deleting, t, words)}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
