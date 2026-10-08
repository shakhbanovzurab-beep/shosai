"use client";

import { Field, FieldContent } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

import { type AppArch, ARCHS_BY_PLATFORM, RELEASE_NOTES_MAX } from "../domain/contract";
import { ARCH_LABELS, MIN_OS_PLACEHOLDER, PLATFORM_LABELS } from "../domain/format";
import type { Draft, FieldName } from "../domain/upload-rules";

/** What each group of form fields receives. */
export type DraftFieldsProps = {
  draft: Draft;
  update: (patch: Partial<Draft>) => void;
  disabled: boolean;
  /** A stable element id for a field name. */
  id: (name: string) => string;
  /** The error to show for a field now, if any. */
  shown: (name: FieldName) => string | undefined;
};

/** Version, architecture, minimum OS, release notes and the mandatory flag. */
export function UploadDetailsFields({
  draft,
  update,
  disabled,
  id,
  shown,
  latest,
}: DraftFieldsProps & { latest: string | null }) {
  return (
    <>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field data-invalid={Boolean(shown("version"))}>
          <FieldLabel htmlFor={id("version")}>Версия</FieldLabel>
          <Input
            id={id("version")}
            value={draft.version}
            onChange={(event) => update({ version: event.target.value })}
            placeholder="2.5.0"
            autoComplete="off"
            spellCheck={false}
            disabled={disabled}
            aria-invalid={Boolean(shown("version"))}
            aria-describedby={id("version-hint")}
          />
          <FieldDescription id={id("version-hint")}>
            {latest ? `SemVer. Последняя в канале: ${latest}.` : "SemVer, например 2.5.0 или 2.5.0-beta.1."}
          </FieldDescription>
          <FieldError>{shown("version")}</FieldError>
        </Field>

        <Field data-invalid={Boolean(shown("arch"))}>
          <FieldLabel htmlFor={id("arch")}>Архитектура</FieldLabel>
          <Select value={draft.arch} onValueChange={(value) => update({ arch: value as AppArch })} disabled={disabled}>
            <SelectTrigger id={id("arch")} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {ARCHS_BY_PLATFORM[draft.platform].map((a) => (
                  <SelectItem key={a} value={a}>
                    {ARCH_LABELS[a]}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldError>{shown("arch")}</FieldError>
        </Field>
      </div>

      <Field data-invalid={Boolean(shown("min_os_version"))}>
        <FieldLabel htmlFor={id("min-os")}>Минимальная версия {PLATFORM_LABELS[draft.platform]}</FieldLabel>
        <Input
          id={id("min-os")}
          value={draft.minOs}
          onChange={(event) => update({ minOs: event.target.value })}
          placeholder={MIN_OS_PLACEHOLDER[draft.platform]}
          autoComplete="off"
          spellCheck={false}
          inputMode="decimal"
          disabled={disabled}
          aria-invalid={Boolean(shown("min_os_version"))}
        />
        <FieldError>{shown("min_os_version")}</FieldError>
      </Field>

      <Field data-invalid={Boolean(shown("release_notes"))}>
        <FieldLabel htmlFor={id("notes")}>Что нового</FieldLabel>
        <Textarea
          id={id("notes")}
          value={draft.notes}
          onChange={(event) => update({ notes: event.target.value })}
          placeholder={"## Что нового\n- …"}
          rows={6}
          maxLength={RELEASE_NOTES_MAX}
          disabled={disabled}
          className="font-mono text-sm"
          aria-invalid={Boolean(shown("release_notes"))}
          aria-describedby={id("notes-hint")}
        />
        <FieldDescription id={id("notes-hint")}>
          Поддерживается Markdown. Текст увидят пользователи в окне обновления.
        </FieldDescription>
        <FieldError>{shown("release_notes")}</FieldError>
      </Field>

      <Field orientation="horizontal">
        <FieldContent>
          <FieldLabel htmlFor={id("mandatory")}>Обязательное обновление</FieldLabel>
          <FieldDescription>Приложение установит его без возможности отложить.</FieldDescription>
        </FieldContent>
        <Switch
          id={id("mandatory")}
          checked={draft.mandatory}
          onCheckedChange={(mandatory) => update({ mandatory })}
          disabled={disabled}
        />
      </Field>
    </>
  );
}
