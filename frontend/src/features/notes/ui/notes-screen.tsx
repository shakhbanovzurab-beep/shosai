"use client";

import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";

import { activeFolderOf } from "../domain/derive-library";
import type { NotesView } from "../domain/notes-href";
import { useFolders, useLibraryCounts } from "../model/folders";
import { retryLibrary, useLibrary } from "../model/library-resource";
import { NotesLibrary } from "./notes-library";

interface NotesScreenProps {
  readonly activeFolderId: string | undefined;
  readonly view: NotesView;
}

// Каркас библиотеки, пока первая страница едет с сервера: те же полосы, что и у карточек ленты.
function LibrarySkeleton() {
  return (
    <div className="flex flex-col gap-8" aria-busy="true">
      <Skeleton className="h-9 w-full max-w-xl" />
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex flex-col gap-2.5">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-4 w-full max-w-3xl" />
        </div>
      ))}
    </div>
  );
}

/** Библиотека встреч человека с сервера: папки, счётчики и встречи текущей папки постранично. */
export function NotesScreen({ activeFolderId: requested, view }: NotesScreenProps) {
  const t = useTranslations("notes");
  const folders = useFolders();
  const counts = useLibraryCounts();
  const folderList = folders.status === "ready" ? folders.data : null;
  const activeFolderId = activeFolderOf(folderList, requested);
  const library = useLibrary(activeFolderId);

  if (library.status === "loading") return <LibrarySkeleton />;
  if (library.status === "error")
    return (
      <LoadError
        title={t("library.loadFailed")}
        message={library.message}
        onRetry={() => void retryLibrary(activeFolderId)}
      />
    );
  return (
    <NotesLibrary
      pages={library.data}
      folders={folderList ?? []}
      counts={counts.status === "ready" ? counts.data : null}
      activeFolderId={activeFolderId}
      view={view}
    />
  );
}
