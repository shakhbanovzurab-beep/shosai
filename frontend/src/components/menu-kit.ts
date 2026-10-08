import type { ComponentType, ReactNode } from "react";

import { ContextMenuGroup } from "@/components/ui/context-menu";
import { ContextMenuCheckboxItem, ContextMenuItem, ContextMenuSeparator } from "@/components/ui/context-menu-items";
import { ContextMenuSub, ContextMenuSubContent, ContextMenuSubTrigger } from "@/components/ui/context-menu-sub";
import { DropdownMenuGroup } from "@/components/ui/dropdown-menu";
import { DropdownMenuCheckboxItem, DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";
import { DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger } from "@/components/ui/dropdown-menu-sub";

type WithChildren = { children?: ReactNode };

/**
 * The menu parts both the right-click menu and the "⋮" dropdown are built from, so one list of
 * items serves both and they can never drift apart.
 */
export type MenuKit = {
  Group: ComponentType<WithChildren>;
  Item: ComponentType<
    WithChildren & { onSelect?: () => void; disabled?: boolean; variant?: "default" | "destructive" }
  >;
  CheckboxItem: ComponentType<
    WithChildren & { checked?: boolean; onCheckedChange?: (checked: boolean) => void; disabled?: boolean }
  >;
  Separator: ComponentType;
  Sub: ComponentType<WithChildren>;
  SubTrigger: ComponentType<WithChildren & { disabled?: boolean }>;
  SubContent: ComponentType<WithChildren & { className?: string }>;
};

export const dropdownKit: MenuKit = {
  Group: DropdownMenuGroup,
  Item: DropdownMenuItem,
  CheckboxItem: DropdownMenuCheckboxItem,
  Separator: DropdownMenuSeparator,
  Sub: DropdownMenuSub,
  SubTrigger: DropdownMenuSubTrigger,
  SubContent: DropdownMenuSubContent,
};

export const contextKit: MenuKit = {
  Group: ContextMenuGroup,
  Item: ContextMenuItem,
  CheckboxItem: ContextMenuCheckboxItem,
  Separator: ContextMenuSeparator,
  Sub: ContextMenuSub,
  SubTrigger: ContextMenuSubTrigger,
  SubContent: ContextMenuSubContent,
};
