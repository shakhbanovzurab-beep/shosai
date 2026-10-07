import type { ReactNode } from "react";

import { FileManager } from "@/features/file-manager";
import { FeatureGate } from "@/features/upgrade";

// FileManager loads the files once for every page here, so they survive opening a folder.
export default function Layout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <FeatureGate feature="file_manager">
      <FileManager>{children}</FileManager>
    </FeatureGate>
  );
}
