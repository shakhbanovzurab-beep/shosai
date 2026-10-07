import { Archive, CircleHelp, File, Inbox, Keyboard, type LucideIcon, Send, Star, Trash2 } from "lucide-react";

/** A sidebar entry; its name is `nav.<id>` in the `mail` catalog. */
export type MailNavItem = {
  id: "inbox" | "priority" | "drafts" | "sent" | "archive" | "trash" | "helpFeedback" | "keyboardShortcuts";
  /** Unread or waiting messages, shown as a badge. */
  count?: number;
  icon: LucideIcon;
  isActive: boolean;
};

type MailNavigation = {
  navMain: MailNavItem[];
  folders: MailNavItem[];
  navFooter: MailNavItem[];
};

export const mailNavigation: MailNavigation = {
  navMain: [
    { id: "inbox", count: 18, icon: Inbox, isActive: true },
    { id: "priority", count: 3, icon: Star, isActive: false },
  ],
  folders: [
    { id: "drafts", count: 9, icon: File, isActive: false },
    { id: "sent", icon: Send, isActive: false },
    { id: "archive", icon: Archive, isActive: false },
    { id: "trash", icon: Trash2, isActive: false },
  ],
  navFooter: [
    { id: "helpFeedback", icon: CircleHelp, isActive: false },
    { id: "keyboardShortcuts", icon: Keyboard, isActive: false },
  ],
};
