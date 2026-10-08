import { PageMeta } from "@/app/root/page-meta";
import { AiModelsScreen } from "@/features/admin-ai-models/ui/ai-models-screen";

export function Component() {
  return (
    <>
      <PageMeta title="AI-модели" />
      <AiModelsScreen />
    </>
  );
}
