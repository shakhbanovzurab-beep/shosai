import { useTranslations } from "use-intl";

import { searchValue } from "@/app/pages/search-record";
import { PageMeta } from "@/app/root/page-meta";
import { parseNotesView } from "@/features/notes/domain/notes-href";
import { NotesScreen } from "@/features/notes/ui/notes-screen";
import { useSearchParams } from "@/lib/navigation";

export function Component() {
  const t = useTranslations("notes");
  const params = useSearchParams();
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <NotesScreen activeFolderId={searchValue(params, "folder")} view={parseNotesView(searchValue(params, "view"))} />
    </>
  );
}
