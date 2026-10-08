import { Box, Grid2x2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import type { SkylineView } from "./use-skyline-engine";

export function SkylineViewToggle({ view, onChange }: { view: SkylineView; onChange: (view: SkylineView) => void }) {
  const t = useTranslations("productivitySkyline");
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      size="sm"
      aria-label={t("views.label")}
      value={view}
      onValueChange={(v) => {
        if (v === "2d" || v === "3d") onChange(v);
      }}
    >
      <ToggleGroupItem value="2d" aria-label={t("views.flat")} title={t("views.flat")}>
        <Grid2x2 />
      </ToggleGroupItem>
      <ToggleGroupItem value="3d" aria-label={t("views.skyline")} title={t("views.skyline")}>
        <Box />
      </ToggleGroupItem>
    </ToggleGroup>
  );
}
