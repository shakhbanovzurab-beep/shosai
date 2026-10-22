"use client";

import { useTranslations } from "use-intl";

import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldContent, FieldLegend, FieldSet } from "@/components/ui/field";
import { FieldDescription, FieldLabel } from "@/components/ui/field-text";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useWorkspace } from "@/features/workspace/model/use-workspace";

import { CHAT_MODES, type ChatMode, type ChatSettings } from "../../domain/contract";

/*
 * Поля, общие для Telegram и Slack: куда идут задачи, что читает Leo, согласие с тем, что Shosai хранит
 * сообщения (ADR 0062). Текст уведомления следует выбранному режиму, дому данных и сроку хранения.
 */

const WHOLE_WORKSPACE = "workspace";

/** Привязка: всё пространство или проект; `null` — всё пространство. */
export function BindingField({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string | null;
  onChange: (projectId: string | null) => void;
}) {
  const t = useTranslations("chatsConnect");
  const { state } = useWorkspace();
  const projects = state.projects.filter((project) => project.status !== "completed");
  return (
    <Field>
      <FieldLabel htmlFor={id}>{t("fields.binding")}</FieldLabel>
      <Select
        value={value ?? WHOLE_WORKSPACE}
        onValueChange={(next) => onChange(next === WHOLE_WORKSPACE ? null : next)}
      >
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value={WHOLE_WORKSPACE}>{t("fields.wholeWorkspace")}</SelectItem>
            {projects.map((project) => (
              <SelectItem key={project.id} value={project.id}>
                <span dir="auto">{project.name}</span>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <FieldDescription>{t("fields.bindingHint")}</FieldDescription>
    </Field>
  );
}

/** Режим чтения: две карточки-варианта с объяснением; `hints` — слова для каждого режима у мессенджера. */
export function ModeField({
  value,
  onChange,
  hints,
}: {
  value: ChatMode;
  onChange: (mode: ChatMode) => void;
  hints: Record<ChatMode, string>;
}) {
  const t = useTranslations("chatsConnect");
  return (
    <FieldSet>
      <FieldLegend variant="label">{t("fields.mode")}</FieldLegend>
      <RadioGroup value={value} onValueChange={(next) => onChange(next === "all" ? "all" : "mentions")}>
        {CHAT_MODES.map((mode) => (
          <FieldLabel key={mode} htmlFor={`chat-mode-${mode}`}>
            <Field orientation="horizontal">
              <RadioGroupItem value={mode} id={`chat-mode-${mode}`} />
              <FieldContent>
                <span className="font-medium">{t(`fields.modes.${mode}`)}</span>
                <FieldDescription>{hints[mode]}</FieldDescription>
              </FieldContent>
            </Field>
          </FieldLabel>
        ))}
      </RadioGroup>
    </FieldSet>
  );
}

/** Согласие с хранением сообщений; без него код не выдаётся (`data_notice_required`). */
export function DataNotice({
  mode,
  settings,
  checked,
  invalid,
  onChange,
}: {
  mode: ChatMode;
  settings: ChatSettings;
  checked: boolean;
  invalid: boolean;
  onChange: (checked: boolean) => void;
}) {
  const t = useTranslations("chatsConnect");
  return (
    <Field orientation="horizontal" data-invalid={invalid || undefined}>
      <Checkbox
        id="chat-data-notice"
        checked={checked}
        aria-invalid={invalid || undefined}
        onCheckedChange={(next) => onChange(next === true)}
      />
      <FieldContent>
        <FieldLabel htmlFor="chat-data-notice" className="font-normal">
          {t("fields.notice", { mode, home: settings.home, days: settings.retention_days })}
        </FieldLabel>
        {invalid ? (
          <FieldDescription className="text-destructive">{t("fields.noticeRequired")}</FieldDescription>
        ) : null}
      </FieldContent>
    </Field>
  );
}
