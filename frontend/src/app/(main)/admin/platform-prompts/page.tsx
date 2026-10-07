import type { Metadata } from "next";

import { PlatformPromptsScreen } from "@/features/admin-platform-prompts";

export const metadata: Metadata = {
  title: "Промты платформы",
  description: "Глобальный системный промт Leo, поведение по умолчанию, правила безопасности и версии.",
  alternates: { canonical: "/admin/platform-prompts" },
};

export default function Page() {
  return <PlatformPromptsScreen />;
}
