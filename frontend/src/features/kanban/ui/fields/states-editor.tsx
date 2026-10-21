"use client";

import { useState } from "react";

import { Plus, X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { STATE_NAME_MAX, STATES_MAX } from "../../domain/stickers-contract";
import { StateColor } from "./state-color";
import { newStateDraft, type StateDraft } from "./state-drafts";

/** Набор состояний: имя и цвет каждого, добавить и убрать; не больше 20. */
export function StatesEditor({ states, onChange }: { states: StateDraft[]; onChange: (states: StateDraft[]) => void }) {
  const t = useTranslations("kanbanFields");
  const [added, setAdded] = useState<string | null>(null);
  const change = (key: string, patch: Partial<StateDraft>) =>
    onChange(states.map((state) => (state.key === key ? { ...state, ...patch } : state)));
  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2">
        {states.map((state) => {
          const name = state.name.trim() || t("dialog.stateName");
          return (
            <li key={state.key} className="flex items-center gap-2">
              <StateColor
                color={state.color}
                label={t("dialog.color", { name })}
                onChange={(color) => change(state.key, { color })}
              />
              <Input
                // Новое состояние сразу ждёт имени: фокус переходит в его поле.
                autoFocus={state.key === added}
                value={state.name}
                maxLength={STATE_NAME_MAX}
                dir="auto"
                aria-label={t("dialog.stateName")}
                placeholder={t("dialog.stateName")}
                onChange={(event) => change(state.key, { name: event.currentTarget.value })}
              />
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t("dialog.removeState", { name })}
                disabled={states.length === 1}
                onClick={() => onChange(states.filter((item) => item.key !== state.key))}
              >
                <X />
              </Button>
            </li>
          );
        })}
      </ul>
      <Button
        variant="ghost"
        size="sm"
        className="self-start"
        disabled={states.length >= STATES_MAX}
        onClick={() => {
          const draft = newStateDraft(states.length);
          setAdded(draft.key);
          onChange([...states, draft]);
        }}
      >
        <Plus data-icon="inline-start" />
        {t("dialog.addState")}
      </Button>
    </div>
  );
}
