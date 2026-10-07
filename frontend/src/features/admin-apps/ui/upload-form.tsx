"use client";

import { type FormEvent, useId, useState, useSyncExternalStore } from "react";

import { Info } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";

import { type AppPlatform, type AppRelease, ARCHS_BY_PLATFORM } from "../domain/contract";
import { platformForFile } from "../domain/release-rules";
import {
  DEFAULT_ARCH,
  type Draft,
  draftErrors,
  type FieldName,
  fileProblem,
  initialDraft,
  latestVersion,
  toMetadata,
} from "../domain/upload-rules";
import { canHashInBrowser } from "../model/sha256";
import { useUpload } from "../model/use-upload";
import { BuildFilePicker } from "./build-file-picker";
import { UploadDetailsFields } from "./upload-details-fields";
import { UploadFooter } from "./upload-footer";
import { UploadTargetFields } from "./upload-target-fields";

const subscribeToNothing = () => () => undefined;
// The server can't know whether the page will run on HTTPS, so it assumes hashing works and the browser corrects it.
const assumeCanHash = () => true;

type UploadFormProps = {
  initialFile: File | null;
  releases: readonly AppRelease[];
  maxBytes: number;
  onBusyChange: (busy: boolean) => void;
  onDone: () => void;
};

export function UploadForm({ initialFile, releases, maxBytes, onBusyChange, onDone }: UploadFormProps) {
  const canHash = useSyncExternalStore(subscribeToNothing, canHashInBrowser, assumeCanHash);
  const ids = useId();
  const id = (name: string) => `${ids}-${name}`;
  const initialProblem = initialFile ? fileProblem(initialFile, maxBytes) : null;

  const [file, setFile] = useState<File | null>(initialProblem ? null : initialFile);
  const [fileError, setFileError] = useState<string | null>(initialProblem);
  const [draft, setDraft] = useState<Draft>(() =>
    initialDraft((initialFile && platformForFile(initialFile.name)) || "macos"),
  );
  const [submitted, setSubmitted] = useState(false);
  const upload = useUpload(onBusyChange, onDone);

  const update = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const errors = draftErrors(draft, releases, file, fileError);
  // The version is checked as it is typed; everything else after the first submit.
  const shown = (name: FieldName) => {
    if (name === "version" && draft.version.trim() !== "") return errors.version;
    return submitted ? errors[name] : undefined;
  };

  const choosePlatform = (platform: AppPlatform) =>
    setDraft((d) => ({
      ...d,
      platform,
      arch: ARCHS_BY_PLATFORM[platform].includes(d.arch) ? d.arch : DEFAULT_ARCH[platform],
    }));

  const selectFile = (next: File) => {
    const problem = fileProblem(next, maxBytes);
    setFileError(problem);
    upload.clearError();
    setFile(problem ? null : next);
    const detected = problem ? null : platformForFile(next.name);
    if (detected) choosePlatform(detected);
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    upload.clearError();
    if (Object.values(errors).some(Boolean) || !file) {
      event.currentTarget.querySelector<HTMLElement>("[aria-invalid=true]")?.focus();
      return;
    }
    void upload.start(file, toMetadata(draft));
  };

  const fieldsProps = { draft, update, disabled: upload.busy, id, shown };

  return (
    <form noValidate onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto p-4">
        <FieldGroup>
          <Field data-invalid={Boolean(shown("file"))}>
            <FieldLabel htmlFor={id("file")}>Файл сборки</FieldLabel>
            <BuildFilePicker
              id={id("file")}
              file={file}
              maxBytes={maxBytes}
              disabled={upload.busy}
              invalid={Boolean(shown("file") || fileError)}
              describedBy={id("file-error")}
              onSelect={selectFile}
              onClear={() => {
                setFile(null);
                setFileError(null);
              }}
            />
            <FieldError id={id("file-error")}>{fileError ?? shown("file")}</FieldError>
          </Field>

          {canHash ? null : (
            <Alert>
              <Info />
              <AlertDescription>
                Страница открыта не по HTTPS, поэтому браузер не может вычислить SHA-256. Контрольную сумму посчитает
                сервер при приёме файла.
              </AlertDescription>
            </Alert>
          )}

          <UploadTargetFields
            draft={draft}
            disabled={upload.busy}
            id={id}
            file={file}
            onPlatformChange={choosePlatform}
            onChannelChange={(channel) => update({ channel })}
          />
          <UploadDetailsFields {...fieldsProps} latest={latestVersion(releases, draft.platform, draft.channel)} />
        </FieldGroup>
      </div>

      <UploadFooter phase={upload.phase} error={upload.error} onCancel={upload.cancel} onClose={onDone} />
    </form>
  );
}
