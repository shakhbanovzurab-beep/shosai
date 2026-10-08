import { PageMeta } from "@/app/root/page-meta";
import { LiveKitScreen } from "@/features/admin-livekit/ui/livekit-screen";

export function Component() {
  return (
    <>
      <PageMeta title="LiveKit — сервер видеозвонков" />
      <LiveKitScreen />
    </>
  );
}
