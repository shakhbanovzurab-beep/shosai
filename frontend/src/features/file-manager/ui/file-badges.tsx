import type { ReactNode } from "react";

import { Folder, Share2 } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";

import type { FileItem } from "../domain/contract";
import { useFileManager } from "./file-manager-store";
import { LeoBadge } from "./leo-badge";

const hidden = (chunks: ReactNode) => <span className="sr-only">{chunks}</span>;
const userText = (chunks: ReactNode) => (
  <span className="truncate" dir="auto">
    {chunks}
  </span>
);

/** Where a file lives and who else answers from it: its folder, Leo, and the workspaces it is shared in. */
export function FileBadges({
  file,
  folderName,
  className,
}: {
  file: FileItem;
  folderName: string | null;
  className?: string;
}) {
  const t = useTranslations("fileManager");
  const format = useFormatter();
  const { sharedIn } = useFileManager();
  const shared = sharedIn(file.id);
  const workspaces = format.list(
    shared.map((w) => w.name),
    { type: "unit", style: "short" },
  );
  return (
    <span className={className}>
      {folderName ? (
        <Badge variant="secondary" className="max-w-40 gap-1">
          <Folder aria-hidden="true" />
          {t.rich("file.inFolder", { folder: folderName, hidden, name: userText })}
        </Badge>
      ) : null}
      <LeoBadge leo={file.leo} />
      {shared.length ? (
        <Badge variant="outline" className="max-w-40 gap-1" title={t("file.sharedIn", { workspaces })}>
          <Share2 aria-hidden="true" />
          {t.rich("file.sharedInHidden", { workspaces, hidden, name: userText })}
        </Badge>
      ) : null}
    </span>
  );
}
