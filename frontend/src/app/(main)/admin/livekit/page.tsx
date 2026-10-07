import type { Metadata } from "next";

import { LiveKitScreen } from "@/features/admin-livekit";

export const metadata: Metadata = {
  title: "LiveKit — сервер видеозвонков",
  alternates: { canonical: "/admin/livekit" },
};

export default function Page() {
  return <LiveKitScreen />;
}
