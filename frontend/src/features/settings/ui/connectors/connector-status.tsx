"use client";

import { Check, ChevronDown, Ellipsis, Unplug } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";
import { Spinner } from "@/components/ui/spinner";

import type { Connector } from "../../domain/connectors-contract";
import { useConnectorActions } from "./connector-actions-context";

function DisconnectItem({ connector }: { connector: Connector }) {
  const t = useTranslations("settingsConnectors");
  const { askDisconnect } = useConnectorActions();
  return (
    <DropdownMenuGroup>
      <DropdownMenuItem variant="destructive" onSelect={() => askDisconnect(connector)}>
        <Unplug />
        {t("disconnect")}
      </DropdownMenuItem>
    </DropdownMenuGroup>
  );
}

function ConnectedMenu({ connector }: { connector: Connector }) {
  const t = useTranslations("settingsConnectors");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" aria-label={t("options", { name: connector.name })}>
          <Check data-icon="inline-start" />
          {t("connected")}
          <ChevronDown data-icon="inline-end" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DisconnectItem connector={connector} />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ReconnectActions({ connector }: { connector: Connector }) {
  const t = useTranslations("settingsConnectors");
  const common = useTranslations("common");
  const { pendingId, connect } = useConnectorActions();
  return (
    <div className="flex items-center gap-1">
      <Button variant="outline" size="sm" disabled={pendingId !== null} onClick={() => connect(connector)}>
        {t("reconnect")}
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={common("actionsFor", { name: connector.name })}>
            <Ellipsis />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DisconnectItem connector={connector} />
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

/** What a row offers: connect, its connected menu, or a reconnect while the app waits for the person. */
export function ConnectorStatus({ connector }: { connector: Connector }) {
  const t = useTranslations("settingsConnectors");
  const { pendingId, connect } = useConnectorActions();
  if (pendingId === connector.id) {
    return (
      <Button variant="outline" size="sm" disabled>
        <Spinner data-icon="inline-start" />
        {t("connecting")}
      </Button>
    );
  }
  if (connector.status === "needs_reconnect") return <ReconnectActions connector={connector} />;
  if (connector.status === "connected") return <ConnectedMenu connector={connector} />;
  return (
    <Button variant="outline" size="sm" disabled={pendingId !== null} onClick={() => connect(connector)}>
      {t("connect")}
    </Button>
  );
}
