"use client";

import { Laptop, Monitor } from "lucide-react";
import { toast } from "sonner";
import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { Device } from "@/features/identity/api/account-data-api";
import { deviceName } from "@/features/identity/domain/device-name";
import { useDeviceSignOut, useDevices } from "@/features/identity/model/devices";
import { apiErrorDescription } from "@/lib/api/error-description";

import { SettingsGroup } from "../settings-row";

function DeviceRow({ device, onSignOut, busy }: { device: Device; onSignOut: () => void; busy: boolean }) {
  const t = useTranslations("settings");
  const format = useFormatter();
  const Icon = device.client_kind === "desktop" ? Monitor : Laptop;
  return (
    <li className="flex items-center gap-3 py-3">
      <Icon className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-2 font-medium text-sm">
          <span dir="auto" className="truncate">
            {deviceName(device.device_label) ??
              t(`devices.kinds.${device.client_kind === "desktop" ? "desktop" : "web"}`)}
          </span>
          {device.current ? <Badge variant="secondary">{t("devices.thisDevice")}</Badge> : null}
        </span>
        <span className="text-muted-foreground text-xs">
          {t("devices.lastActive", { time: format.relativeTime(new Date(device.last_used_at)) })}
          {device.ip ? <span dir="ltr"> · {device.ip}</span> : null}
        </span>
      </div>
      {device.current ? null : (
        <Button variant="outline" size="sm" disabled={busy} onClick={onSignOut}>
          {t("devices.signOut")}
        </Button>
      )}
    </li>
  );
}

/** Где открыт аккаунт: выйти на одном устройстве или на всех, кроме этого. */
export function Devices() {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  const { devices, isPending, isError, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } = useDevices();
  const { one, others } = useDeviceSignOut();
  const failed = (error: unknown) =>
    toast.error(t("devices.signOutFailed"), { description: apiErrorDescription(error) });

  const signOutOthers = () =>
    others.mutate(undefined, {
      onSuccess: (ended) => toast.success(t("devices.signedOutOthers", { count: ended })),
      onError: failed,
    });

  return (
    <SettingsGroup title={t("devices.title")}>
      <p className="text-muted-foreground text-sm">{t("devices.description")}</p>
      {isPending ? <Spinner className="my-3" /> : null}
      {isError ? (
        <div role="alert" className="flex items-center gap-3 py-2 text-sm">
          {t("devices.loadFailed")}
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            {common("actions.retry")}
          </Button>
        </div>
      ) : null}
      <ul className="divide-y">
        {devices.map((device) => (
          <DeviceRow
            key={device.id}
            device={device}
            busy={one.isPending}
            onSignOut={() => one.mutate(device.id, { onError: failed })}
          />
        ))}
      </ul>
      <div className="flex flex-wrap gap-2 pt-2">
        {hasNextPage ? (
          <Button variant="ghost" size="sm" disabled={isFetchingNextPage} onClick={() => void fetchNextPage()}>
            {t("devices.more")}
          </Button>
        ) : null}
        {devices.some((device) => !device.current) ? (
          <Button variant="outline" size="sm" disabled={others.isPending} onClick={signOutOthers}>
            {others.isPending ? <Spinner data-icon="inline-start" /> : null}
            {t("devices.signOutOthers")}
          </Button>
        ) : null}
      </div>
    </SettingsGroup>
  );
}
