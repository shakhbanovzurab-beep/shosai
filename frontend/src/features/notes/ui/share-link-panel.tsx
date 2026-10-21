"use client";

import { Copy } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Field, FieldContent, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";
import { FieldDescription, FieldLabel } from "@/components/ui/field-text";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import {
  DEFAULT_SHARE_SETTINGS,
  expiryDays,
  SHARE_EXPIRIES,
  type ShareExpiry,
  type ShareLinkSettings,
} from "../domain/share-link";
import { copyShareLink, retryShareLink, stopSharing, updateShareLink, useShareLink } from "../model/share-link";

const TOGGLES = ["showTranscript", "showNames", "allowComments"] as const;

/** The popover only opens in the browser, so the page's origin is there to build the full address. */
const absoluteUrl = (path: string) =>
  typeof window === "undefined" ? path : new URL(path, window.location.origin).href;

/** Share by link: people outside the meeting open the notes, with what the link shows set here. */
export function ShareLinkPanel({ noteId }: { readonly noteId: string }) {
  const t = useTranslations("notesShare");
  const notes = useTranslations("notes");
  const common = useTranslations("common");
  const words = { share: t, notes };
  const format = useFormatter();
  const state = useShareLink(noteId);
  if (state.status === "loading") return <Skeleton className="h-16" />;
  if (state.status === "error")
    return (
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">{t("panel.loadFailed")}</span>
        <Button variant="outline" size="xs" onClick={() => void retryShareLink(noteId)}>
          {common("actions.retry")}
        </Button>
      </div>
    );

  const { link } = state.data;
  const url = link ? absoluteUrl(link.path) : "";
  const change = (patch: Partial<ShareLinkSettings>) =>
    link ? void updateShareLink(noteId, { ...link.settings, ...patch }, words) : undefined;
  const expiryLabel = (expiry: ShareExpiry) => {
    const days = expiryDays(expiry);
    return days === null ? t("panel.never") : t("panel.days", { count: days });
  };
  const toggleDescription = (toggle: (typeof TOGGLES)[number]) =>
    toggle === "showNames"
      ? t("panel.toggles.showNames.description", {
          first: t("panel.speaker", { order: 1 }),
          second: t("panel.speaker", { order: 2 }),
        })
      : t(`panel.toggles.${toggle}.description`);

  return (
    <div className="flex flex-col gap-4">
      <Field orientation="horizontal">
        <FieldContent>
          <FieldLabel htmlFor="share-link-on">{t("panel.anyone")}</FieldLabel>
          <FieldDescription>{t("panel.anyoneHint")}</FieldDescription>
        </FieldContent>
        <Switch
          id="share-link-on"
          checked={link !== null}
          onCheckedChange={(on) =>
            void (on ? updateShareLink(noteId, DEFAULT_SHARE_SETTINGS, words) : stopSharing(noteId, words))
          }
        />
      </Field>
      {link ? (
        <>
          <InputGroup>
            {/* An address reads left to right in every language. */}
            <InputGroupInput
              readOnly
              dir="ltr"
              value={url}
              aria-label={t("panel.linkLabel")}
              onFocus={(event) => event.currentTarget.select()}
            />
            <InputGroupAddon align="inline-end">
              <InputGroupButton onClick={() => void copyShareLink(url, common)}>
                <Copy />
                {common("actions.copyLink")}
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
          <Separator />
          <FieldGroup className="gap-4">
            {TOGGLES.map((toggle) => (
              <Field key={toggle} orientation="horizontal">
                <FieldContent>
                  <FieldLabel htmlFor={`share-${toggle}`}>{t(`panel.toggles.${toggle}.label`)}</FieldLabel>
                  <FieldDescription>{toggleDescription(toggle)}</FieldDescription>
                </FieldContent>
                <Switch
                  id={`share-${toggle}`}
                  checked={link.settings[toggle]}
                  onCheckedChange={(checked) => change({ [toggle]: checked })}
                />
              </Field>
            ))}
            <FieldSet className="gap-2">
              <FieldLegend variant="label">{t("panel.expires")}</FieldLegend>
              <ToggleGroup
                type="single"
                variant="outline"
                size="sm"
                spacing={0}
                value={link.settings.expiry}
                onValueChange={(value) => (value ? change({ expiry: value as ShareExpiry }) : undefined)}
                className="w-full"
              >
                {SHARE_EXPIRIES.map((expiry) => (
                  <ToggleGroupItem key={expiry} value={expiry} className="flex-1">
                    {expiryLabel(expiry)}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
              <FieldDescription>
                {link.expiresAt
                  ? t("panel.stopsOn", { date: format.dateTime(new Date(link.expiresAt), "shortDateTime") })
                  : t("panel.keepsWorking")}
              </FieldDescription>
            </FieldSet>
          </FieldGroup>
        </>
      ) : null}
    </div>
  );
}
