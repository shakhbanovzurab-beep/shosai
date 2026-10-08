import { PageMeta } from "@/app/root/page-meta";
import { PlatformPromptsScreen } from "@/features/admin-platform-prompts/ui/platform-prompts-screen";

export function Component() {
  return (
    <>
      <PageMeta
        title="Промты платформы"
        description="Глобальный системный промт Leo, поведение по умолчанию, правила безопасности и версии."
      />
      <PlatformPromptsScreen />
    </>
  );
}
