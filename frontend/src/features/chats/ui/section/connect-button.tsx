"use client";

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
}: {
  settings: ChatSettings | null;
  full: boolean;
  onOpen: () => void;
}) {
  const t = useTranslations("chats");
  return (
    <Button
      size="sm"
      disabled={settings === null || full}
      onPointerEnter={prefetchConnect}
      onFocus={prefetchConnect}
      onClick={onOpen}
    >
      <Plus data-icon="inline-start" />
      {t("section.connect")}
    </Button>
  );
}
