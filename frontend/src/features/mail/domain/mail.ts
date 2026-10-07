export type Recipient = {
  name: string;
  email: string;
};

/** Which file-type icon an attachment shows. */
export type AttachmentKind = "figma" | "document" | "image";

export type Attachment = {
  id: string;
  name: string;
  /** Size in bytes. */
  size: number;
  kind: AttachmentKind;
};

export type MailFolder = "inbox" | "drafts" | "sent" | "archive" | "trash";

export type Mail = {
  id: string;
  accountId: number;
  from: Recipient;
  to: Recipient[];
  cc?: Recipient[];
  subject: string;
  body: string;
  receivedAt: string;
  folder: MailFolder;
  isRead: boolean;
  isPinned: boolean;
  isPriority: boolean;
  labels: string[];
  attachments?: Attachment[];
  messageCount?: number;
  /** When the user last replied to this email from the inbox. */
  repliedAt?: string;
};

export type MailAccount = {
  id: number;
  /** The mailbox owner's name, as they set it. */
  name: string;
  email: string;
};
