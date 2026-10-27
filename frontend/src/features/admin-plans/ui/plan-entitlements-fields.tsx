"use client";

import { FieldLegend, FieldSet } from "@/components/ui/field";

import {
  PLAN_CAPABILITIES,
  PLAN_CAPABILITY_LABEL,
  type PlanCapabilities,
  type PlanCapability,
} from "../domain/contract";
import type { PlanTextKey } from "../domain/plan-form-values";
import { SwitchField, TextField } from "./form-field";

const CAPABILITY_HINT: Record<PlanCapability, string> = {
  shared_workspace: "Общие встречи, файлы и база знаний команды.",
  member_management: "Приглашение и удаление участников, роли в команде.",
  centralized_billing: "Один счёт за всех участников.",
  sso: "Вход через корпоративного провайдера (SAML, OIDC).",
  admin_controls: "Роли, политики доступа и журнал аудита для администраторов компании.",
  priority_support: "Ответ поддержки вне общей очереди.",
  usage_analytics: "Отчёты об использовании по сотрудникам и командам.",
};

type TextProps = (key: PlanTextKey) => {
  id: string;
  value: string;
  error: string | undefined;
  disabled: boolean;
  onChange: (event: { target: { value: string } }) => void;
};

type PlanEntitlementsFieldsProps = {
  text: TextProps;
  capabilities: PlanCapabilities;
  disabled: boolean;
  onCapability: (capability: PlanCapability, enabled: boolean) => void;
};

/** What the plan includes: meeting minutes, storage, people in a call, enterprise extras. */
export function PlanEntitlementsFields({ text, capabilities, disabled, onCapability }: PlanEntitlementsFieldsProps) {
  return (
    <>
      <FieldSet>
        <FieldLegend>Лимиты</FieldLegend>
        <p className="-mt-2 text-muted-foreground text-sm">Пустое поле — без ограничений, 0 — недоступно.</p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <TextField
            label="Минуты встреч в месяц"
            inputMode="numeric"
            description="Когда минуты закончатся, встречи остановятся до следующего месяца."
            {...text("meeting_minutes_per_month")}
          />
          <TextField label="File Manager, ГБ" inputMode="numeric" {...text("file_manager_gb")} />
          <TextField
            label="База знаний, МБ"
            inputMode="numeric"
            description="1024 МБ показываются как 1 ГБ."
            {...text("knowledge_base_mb")}
          />
          <TextField
            label="Участников в звонке"
            inputMode="numeric"
            description="Пустое поле — потолок платформы (50)."
            {...text("room_participants")}
          />
        </div>
      </FieldSet>
      <FieldSet>
        <FieldLegend>Возможности для команд и Enterprise</FieldLegend>
        <div className="grid gap-3 sm:grid-cols-2">
          {PLAN_CAPABILITIES.map((capability) => (
            <SwitchField
              key={capability}
              id={`plan-capability-${capability.replaceAll("_", "-")}`}
              label={PLAN_CAPABILITY_LABEL[capability]}
              description={CAPABILITY_HINT[capability]}
              checked={capabilities[capability]}
              disabled={disabled}
              onCheckedChange={(checked) => onCapability(capability, checked)}
            />
          ))}
        </div>
      </FieldSet>
    </>
  );
}
