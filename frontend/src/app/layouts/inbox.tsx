import { Outlet } from "react-router";

import { InboxLayout } from "@/features/mail/ui/inbox-layout";

/** У отдельного почтового ящика (/app/inbox) своя рамка, не панели. */
export function Component() {
  return (
    <InboxLayout>
      <Outlet />
    </InboxLayout>
  );
}
