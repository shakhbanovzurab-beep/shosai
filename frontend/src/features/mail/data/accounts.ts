import type { MailAccount, Recipient } from "../domain/mail";

export const arhamKhan: Recipient = {
  name: "Arham Khan",
  email: "arham@lumen.so",
};

export const weblabsStudio: Recipient = {
  name: "Weblabs Studio",
  email: "contact@weblabs.studio",
};

export const accounts: MailAccount[] = [
  {
    id: 1,
    name: "Arham Khan",
    email: "arham@lumen.so",
  },
  {
    id: 2,
    name: "Weblabs Studio",
    email: "contact@weblabs.studio",
  },
];
