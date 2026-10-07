"use client";

import { useRef, useState, useTransition } from "react";

import { cn } from "cn";
import { Camera } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { getInitials } from "@/lib/utils";

import type { UserSettings } from "../../domain/settings-contract";
import { removeAvatar, uploadAvatar } from "../../model/account-actions";

/** Profile photo: pick or drop any image; it's cropped square and scaled down before upload. */
export function AvatarEditor({ settings }: { settings: UserSettings }) {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  const locale = useLocale();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isOver, setIsOver] = useState(false);
  const [pending, startTransition] = useTransition();

  const upload = (file: File | undefined) => {
    if (!file) return;
    startTransition(() => uploadAvatar(file, t, locale));
  };

  const remove = () => startTransition(() => removeAvatar(t));

  return (
    <div className="flex items-center gap-4">
      <button
        type="button"
        aria-label={t("avatar.change")}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setIsOver(true);
        }}
        onDragLeave={() => setIsOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsOver(false);
          upload(event.dataTransfer.files[0]);
        }}
        className={cn(
          "group relative size-16 shrink-0 cursor-pointer rounded-xl focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2",
          isOver && "ring-2 ring-primary ring-offset-2",
        )}
      >
        <Avatar className="size-16 rounded-xl">
          {settings.avatar_url ? <AvatarImage src={settings.avatar_url} alt="" className="object-cover" /> : null}
          <AvatarFallback className="rounded-xl text-lg">{getInitials(settings.full_name || "?")}</AvatarFallback>
        </Avatar>
        <span
          className={cn(
            "absolute inset-0 grid place-items-center rounded-xl bg-black/50 text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100",
            (pending || isOver) && "opacity-100",
          )}
          aria-hidden="true"
        >
          {pending ? <Spinner className="size-5" /> : <Camera className="size-5" />}
        </span>
      </button>
      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex min-w-0 flex-col">
          <span dir="auto" className="truncate font-medium">
            {settings.full_name}
          </span>
          <span className="text-muted-foreground text-xs">{t("avatar.hint")}</span>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={pending} onClick={() => inputRef.current?.click()}>
            {t("avatar.upload")}
          </Button>
          {settings.avatar_url ? (
            <Button size="sm" variant="ghost" disabled={pending} onClick={remove}>
              {common("actions.remove")}
            </Button>
          ) : null}
        </div>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          upload(event.currentTarget.files?.[0]);
          event.currentTarget.value = "";
        }}
      />
    </div>
  );
}
