import type { Metadata } from "next";

import { AiModelsScreen } from "@/features/admin-ai-models";

export const metadata: Metadata = {
  title: "AI-модели",
  alternates: { canonical: "/admin/ai-models" },
};

export default function Page() {
  return <AiModelsScreen />;
}
