"use client";

import { Check, ChevronDown, Unplug } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { Connector } from "../../domain/connectors-contract";
import { connectorsResource } from "../../model/settings-resources";
import { useConnectorOAuth } from "../../model/use-connector-oauth";
import { SectionState } from "../section-state";
import { ConnectorLogo } from "./connector-logo";

interface ConnectorStatusProps {
  readonly connector: Connector;
  readonly isPending: boolean;
  readonly isBusy: boolean;
  readonly onConnect: (connector: Connector) => void;
  readonly onDisconnect: (connector: Connector) => void;
}

function ConnectorStatus({ connector, isPending, isBusy, onConnect, onDisconnect }: ConnectorStatusProps) {
  const t = useTranslations("settingsConnectors");
  if (isPending) {
    return (
      <Button variant="outline" size="sm" disabled>
        <Spinner data-icon="inline-start" />
        {t("connecting")}
      </Button>
    );
  }
  if (!connector.connected) {
    return (
      <Button variant="outline" size="sm" disabled={isBusy} onClick={() => onConnect(connector)}>
        {t("connect")}
      </Button>
    );
  }
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
        <DropdownMenuItem variant="destructive" onSelect={() => onDisconnect(connector)}>
          <Unplug />
          {t("disconnect")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Apps Leo can use, connected through each provider's OAuth 2.0 consent; laid out like Claude's list. */
export function ConnectorsSection() {
  const t = useTranslations("settingsConnectors");
  const state = usePollingResource(connectorsResource);
  const { pendingId, connect, disconnect } = useConnectorOAuth();

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">{t("description")}</p>
      <SectionState state={state} onRetry={() => void connectorsResource.refresh()}>
        {({ connectors }) => (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-start">{t("columns.connector")}</TableHead>
                <TableHead className="w-36 text-start">{t("columns.type")}</TableHead>
                <TableHead className="w-40 text-start">{t("columns.status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {connectors.map((connector) => (
                <TableRow key={connector.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <ConnectorLogo id={connector.id} />
                      <div className="flex min-w-0 flex-col">
                        <span className="font-medium">{connector.name}</span>
                        {connector.account ? (
                          <span dir="auto" className="truncate text-muted-foreground text-xs">
                            {connector.account}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{t(`categories.${connector.category}`)}</TableCell>
                  <TableCell>
                    <ConnectorStatus
                      connector={connector}
                      isPending={pendingId === connector.id}
                      isBusy={pendingId !== null}
                      onConnect={(c) => void connect(c)}
                      onDisconnect={(c) => void disconnect(c)}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </SectionState>
    </div>
  );
}
