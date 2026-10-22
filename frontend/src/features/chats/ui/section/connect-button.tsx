"use client";

import type { Ref } from "react";

import { Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { lazyComponent } from "@/lib/lazy-component";

import type { ChatSettings } from "../../domain/contract";

/*
 * «Подключить чат» и его окно. Окно — отдельный чанк, который грузится, когда к кнопке подводят указатель или
 * фокус, и показывается при первом открытии.
 */

const loadConnect = () => import("../connect/connect-dialog");
const prefetchConnect = () => void loadConnect();
const LazyConnectDialog = lazyComponent(() => loadConnect().then((m) => m.ConnectDialog));

/** Окно подключения из своего чанка. */
export function ConnectDialog(props: Parameters<typeof LazyConnectDialog>[0]) {
  return <LazyConnectDialog {...props} />;
}

export function ConnectButton({
  settings,
  full,
  onOpen,
  ref,
}: {
  settings: ChatSettings | null;
  full: boolean;
  onOpen: () => void;
  ref?: Ref<HTMLButtonElement>;
}) {
  const t = useTranslations("chats");
  return (
    <Button
      ref={ref}
      data-chats-action="connect"
      size="sm"
      // Установка без мессенджеров с путём подключения: окну нечего предложить.
      disabled={settings === null || full || settings.messengers.length === 0}
      onPointerEnter={prefetchConnect}
      onFocus={prefetchConnect}
      onClick={onOpen}
    >
      <Plus data-icon="inline-start" />
      {t("section.connect")}
    </Button>
  );
}
