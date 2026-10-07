import type { ComponentType, ReactNode } from "react";

import {
  ContextMenuCheckboxItem,
  ContextMenuGroup,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
} from "@/components/ui/context-menu";
import {
  DropdownMenuCheckboxItem,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu";

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
