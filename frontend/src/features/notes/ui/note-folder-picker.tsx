"use client";

import { useState } from "react";

import { cn } from "cn";
import { Folder, FolderPlus } from "lucide-react";
import { useTranslations } from "use-intl";

import { META_VALUE_BUTTON, MetaItem } from "@/components/meta-item";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import type { NoteFolder } from "../domain/types";
import { folderActions, useFolders } from "../model/folders";
import { FOLDER_DOT_CLASSES } from "./folder-color-classes";
import { FolderNameInput } from "./folder-name-input";

const Dot = ({ folder }: { folder: NoteFolder }) => (
  <span className={cn("size-2 shrink-0 rounded-full", FOLDER_DOT_CLASSES[folder.color])} aria-hidden="true" />
);

/** Папка встречи под заголовком; открывает список с поиском, чтобы переложить встречу или завести ей новую папку. */
export function NoteFolderPicker({ noteId, folderId }: { noteId: string; folderId: string | undefined }) {
  const t = useTranslations("notes");
  const state = useFolders();
  const folders = state.status === "ready" ? state.data : [];
  const folder = folders.find((f) => f.id === folderId);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [naming, setNaming] = useState(false);
  const newName = query.trim();

  const openChange = (next: boolean) => {
    setOpen(next);
    if (next) return;
    setQuery("");
    setNaming(false);
  };

  const moveTo = (target: NoteFolder | null) => {
    openChange(false);
    if (target?.id !== folder?.id) void folderActions.move(noteId, target, t);
  };

  const moveToNew = async (name: string) => {
    const created = await folderActions.create(name, t);
    if (created) moveTo(created);
  };

  return (
    <MetaItem icon={Folder} label={t("fields.folder")} className="shrink-0">
      <Popover open={open} onOpenChange={openChange}>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="xs" className={META_VALUE_BUTTON}>
            {folder ? <Dot folder={folder} /> : null}
            {folder ? (
              <span dir="auto" className="max-w-40 truncate">
                {folder.name}
              </span>
            ) : (
              <span className="max-w-40 truncate">{t("folders.add")}</span>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-64 p-0" aria-label={t("folders.moveTo")}>
          <Command>
            <CommandInput placeholder={t("folders.search")} value={query} onValueChange={setQuery} />
            <CommandList>
              <CommandEmpty>{t("folders.noMatch")}</CommandEmpty>
              <CommandGroup>
                <CommandItem
                  value="no-folder"
                  keywords={[t("folders.none")]}
                  data-checked={!folder}
                  onSelect={() => moveTo(null)}
                >
                  {t("folders.none")}
                </CommandItem>
                {folders.map((item) => (
                  <CommandItem
                    key={item.id}
                    value={item.id}
                    keywords={[item.name]}
                    data-checked={item.id === folder?.id}
                    onSelect={() => moveTo(item)}
                  >
                    <Dot folder={item} />
                    <span dir="auto" className="truncate">
                      {item.name}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
              <CommandSeparator alwaysRender />
              <CommandGroup forceMount>
                <CommandItem
                  forceMount
                  value="new-folder"
                  onSelect={() => (newName ? void moveToNew(newName) : setNaming(true))}
                >
                  <FolderPlus />
                  <span className="truncate">
                    {newName ? t("folders.newNamed", { name: newName }) : t("folders.newMenu")}
                  </span>
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
          {naming ? (
            <div className="flex items-center gap-2 border-t px-3 py-2.5 text-sm">
              <FolderPlus className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <FolderNameInput
                initialName={t("folders.defaultName")}
                onSubmit={(name) => void moveToNew(name)}
                onCancel={() => setNaming(false)}
              />
            </div>
          ) : null}
        </PopoverContent>
      </Popover>
    </MetaItem>
  );
}
