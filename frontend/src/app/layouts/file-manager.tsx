import { Outlet } from "react-router";

import { FileManager } from "@/features/file-manager/ui/file-manager";
import { FeatureGate } from "@/features/upgrade/ui/feature-gate";

// FileManager loads the files once for every page here, so they survive opening a folder.
export function Component() {
  return (
    <FeatureGate feature="file_manager">
      <FileManager>
        <Outlet />
      </FileManager>
    </FeatureGate>
  );
}
