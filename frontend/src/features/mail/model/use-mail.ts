import { create } from "zustand";

import { mails } from "../data/mails";
import type { Mail } from "../domain/mail";

type Config = {
  selected: Mail["id"] | null;
};

type MailStore = {
  mail: Config;
  setMail: (mail: Config) => void;
};

const useMailStore = create<MailStore>((set) => ({
  mail: {
    selected: mails[0].id,
  },
  setMail: (mail) => set({ mail }),
}));

export function useMail() {
  const mail = useMailStore((state) => state.mail);
  const setMail = useMailStore((state) => state.setMail);

  return [mail, setMail] as const;
}
