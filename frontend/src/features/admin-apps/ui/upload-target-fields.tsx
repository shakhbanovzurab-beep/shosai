"use client";

import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import {
  APP_PLATFORMS,
  type AppPlatform,
  EXTENSIONS_BY_PLATFORM,
  RELEASE_CHANNELS,
  type ReleaseChannel,
} from "../domain/contract";
import { CHANNEL_LABELS, PLATFORM_LABELS } from "../domain/format";
import { fileExtension, platformForFile } from "../domain/release-rules";
import type { DraftFieldsProps } from "./upload-details-fields";

type UploadTargetFieldsProps = Pick<DraftFieldsProps, "draft" | "disabled" | "id"> & {
  file: File | null;
  onPlatformChange: (platform: AppPlatform) => void;
  onChannelChange: (channel: ReleaseChannel) => void;
};

/** Platform (detected from the file, can be overridden) and channel. */
export function UploadTargetFields({
  draft,
  disabled,
  id,
  file,
  onPlatformChange,
  onChannelChange,
}: UploadTargetFieldsProps) {
  const detected = file ? platformForFile(file.name) : null;
  const mismatch = file !== null && !EXTENSIONS_BY_PLATFORM[draft.platform].includes(fileExtension(file.name));

  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <Field>
        <FieldLabel id={id("platform-label")}>Платформа</FieldLabel>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={draft.platform}
          disabled={disabled}
          aria-labelledby={id("platform-label")}
          onValueChange={(value) => (value ? onPlatformChange(value as AppPlatform) : undefined)}
        >
          {APP_PLATFORMS.map((p) => (
            <ToggleGroupItem key={p} value={p}>
              {PLATFORM_LABELS[p]}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <FieldDescription>
          {mismatch && file
            ? `Обычно файлы ${fileExtension(file.name)} — сборки для ${PLATFORM_LABELS[detected ?? draft.platform]}. Проверьте платформу.`
            : "Определяется по расширению файла."}
        </FieldDescription>
      </Field>

      <Field>
        <FieldLabel id={id("channel-label")}>Канал</FieldLabel>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={draft.channel}
          disabled={disabled}
          aria-labelledby={id("channel-label")}
          onValueChange={(value) => (value ? onChannelChange(value as ReleaseChannel) : undefined)}
        >
          {RELEASE_CHANNELS.map((c) => (
            <ToggleGroupItem key={c} value={c}>
              {CHANNEL_LABELS[c]}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Field>
    </div>
  );
}
