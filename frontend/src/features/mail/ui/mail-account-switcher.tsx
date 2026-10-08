"use client";

import type * as React from "react";

import { cn } from "cn";
import { Check, EllipsisVertical, LogOut, Settings2, UserPlus, UsersRound } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useDirection } from "@/components/ui/direction";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu-items";
import { useSidebar } from "@/components/ui/sidebar";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { getInitials } from "@/lib/utils";

import { accounts } from "../data/accounts";
import type { MailAccount } from "../domain/mail";

type MailAccountSwitcherProps = {
  selectedAccount: MailAccount;
  onSelectAccount: (account: MailAccount) => void;
};

/** The mailbox switcher at the top of the sidebar: toggles when expanded, one menu when collapsed. */
export function MailAccountSwitcher({ selectedAccount, onSelectAccount }: MailAccountSwitcherProps) {
  const t = useTranslations("mail.accounts");
  const common = useTranslations("common");
  const { state } = useSidebar();
  // The menu opens away from the sidebar, towards the content.
  const side = useDirection() === "rtl" ? "left" : "right";

  if (state === "collapsed") {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            className={accountTriggerClassName}
            aria-label={common("actionsFor", { name: selectedAccount.name })}
          >
            <AccountMarker account={selectedAccount} isSelected />
          </Button>
        </DropdownMenuTrigger>
        <AccountMenuContent
          selectedAccountId={selectedAccount.id}
          onSelectAccount={onSelectAccount}
          showAccounts
          side={side}
          align="start"
        />
      </DropdownMenu>
    );
  }

  return (
    <>
      <ToggleGroup
        type="single"
        value={String(selectedAccount.id)}
        onValueChange={(value) => {
          const account = accounts.find((item) => item.id === Number(value));

          if (account) {
            onSelectAccount(account);
          }
        }}
        spacing={2}
      >
        {accounts.map((account) => (
          <ToggleGroupItem
            key={account.id}
            className={accountTriggerClassName}
            value={String(account.id)}
            aria-label={t("switchTo", { name: account.name })}
          >
            <AccountMarker account={account} />
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={t("menu")}>
            <EllipsisVertical />
          </Button>
        </DropdownMenuTrigger>
        <AccountMenuContent selectedAccountId={selectedAccount.id} onSelectAccount={onSelectAccount} />
      </DropdownMenu>
    </>
  );
}

const accountTriggerClassName = cn(
  "relative size-7 min-w-7 rounded-sm p-0 transition-colors",
  "bg-primary text-primary-foreground text-xs hover:bg-primary/90 hover:text-primary-foreground",
  "data-[state=on]:bg-primary data-[state=on]:text-primary-foreground",
  "data-[state=on]:ring data-[state=on]:ring-green-600",
  "focus-visible:border-transparent focus-visible:ring-0",
);

function AccountMarker({ account, isSelected = false }: { account: MailAccount; isSelected?: boolean }) {
  return (
    <>
      {getInitials(account.name).slice(0, 1)}
      <span
        className={cn(
          "absolute end-0 bottom-0 z-10 hidden size-2.5 items-center justify-center rounded-full bg-green-600 text-primary-foreground ring-[1.25px] ring-background group-data-[state=on]/toggle:flex",
          isSelected && "flex",
        )}
      >
        <Check className="size-2" />
      </span>
    </>
  );
}

function AccountMenuContent({
  selectedAccountId,
  onSelectAccount,
  showAccounts = false,
  ...props
}: {
  selectedAccountId: number;
  onSelectAccount: (account: MailAccount) => void;
  showAccounts?: boolean;
} & Pick<React.ComponentProps<typeof DropdownMenuContent>, "align" | "side">) {
  const t = useTranslations("mail.accounts");

  return (
    <DropdownMenuContent className="w-56" {...props}>
      {showAccounts && (
        <>
          <DropdownMenuLabel>{t("title")}</DropdownMenuLabel>
          <DropdownMenuGroup>
            <DropdownMenuRadioGroup
              value={String(selectedAccountId)}
              onValueChange={(value) => {
                const account = accounts.find((item) => item.id === Number(value));

                if (account) {
                  onSelectAccount(account);
                }
              }}
            >
              {accounts.map((account) => (
                <DropdownMenuRadioItem key={account.id} value={String(account.id)}>
                  <div className="flex min-w-0 flex-col">
                    <span dir="auto">{account.name}</span>
                    <span className="truncate text-muted-foreground text-xs">{account.email}</span>
                  </div>
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
        </>
      )}
      <DropdownMenuGroup>
        <DropdownMenuItem>
          <UserPlus />
          {t("add")}
        </DropdownMenuItem>
        <DropdownMenuItem>
          <UsersRound />
          {t("manage")}
        </DropdownMenuItem>
        <DropdownMenuItem>
          <Settings2 />
          {t("settings")}
        </DropdownMenuItem>
      </DropdownMenuGroup>
      <DropdownMenuSeparator />
      <DropdownMenuGroup>
        <DropdownMenuItem>
          <LogOut className="rtl:-scale-x-100" />
          {t("signOut")}
        </DropdownMenuItem>
      </DropdownMenuGroup>
    </DropdownMenuContent>
  );
}
