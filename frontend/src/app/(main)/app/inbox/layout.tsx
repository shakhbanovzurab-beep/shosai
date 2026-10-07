import type { ReactNode } from "react";

import { InboxLayout } from "@/features/mail";

export default function Layout({ children }: Readonly<{ children: ReactNode }>) {
  return <InboxLayout>{children}</InboxLayout>;
}
