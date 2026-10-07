import type { Metadata } from "next";

import { MailPreview } from "@/features/mail";

export const metadata: Metadata = {
  robots: {
    index: false,
    follow: true,
  },
};

export default function Page() {
  return <MailPreview />;
}
