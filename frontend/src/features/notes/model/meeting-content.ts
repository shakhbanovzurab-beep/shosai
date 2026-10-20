import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { contentApi, type TranscriptLineOut } from "../api/note-content-api";
import type { MeetingSpeaker, Voice } from "../domain/meeting-page";
import { voiceOf } from "../domain/meeting-page";
import { type FlatMapNode, mindMapTree } from "../domain/mind-map-tree";
import { isApiCode } from "../domain/problems";
import type { MindMapNode, TranscriptLine } from "../domain/types";

/*
 * Расшифровка и карта встречи читаются целиком, страницами сервера: поиск, экспорт и статистика спикеров
 * работают по всей встрече. По ресурсу на встречу; после новых записей их перечитывают.
 */

async function everyLine(id: string): Promise<TranscriptLineOut[]> {
  const lines: TranscriptLineOut[] = [];
  let cursor: string | undefined;
  do {
    const page = await contentApi.transcript(id, cursor);
    lines.push(...page.items);
    cursor = page.next_cursor ?? undefined;
  } while (cursor);
  return lines;
}

async function everyNode(id: string): Promise<MindMapNode | null> {
  const nodes: FlatMapNode[] = [];
  let cursor: string | undefined;
  do {
    const page = await contentApi.map(id, cursor).catch((error: unknown) => {
      // Карты ещё нет — записи не написаны: это не сбой, страница так и скажет.
      if (isApiCode(error, "map_not_found")) return null;
      throw error;
    });
    if (page === null) return null;
    nodes.push(...page.items.map((node) => ({ id: node.id, parentId: node.parent_id, label: node.label })));
    cursor = page.next_cursor ?? undefined;
  } while (cursor);
  return mindMapTree(nodes);
}

function keyed<T>(load: (id: string) => Promise<T>) {
  const resources = new Map<string, PollingResource<T>>();
  return (id: string) => {
    let resource = resources.get(id);
    if (!resource) {
      resource = createPollingResource(() => load(id));
      resources.set(id, resource);
    }
    return resource;
  };
}

const transcriptOf = keyed(everyLine);
const mapOf = keyed(everyNode);

export const useTranscript = (id: string) => usePollingResource(transcriptOf(id));
export const useMindMap = (id: string) => usePollingResource(mapOf(id));
export const retryTranscript = (id: string) => transcriptOf(id).refresh();
export const retryMindMap = (id: string) => mapOf(id).refresh();

/** После новых записей встречи (запись с голосами, переписанная запись) расшифровка и карта читаются заново. */
export function refreshContent(id: string) {
  void transcriptOf(id).refresh();
  void mapOf(id).refresh();
}

/** Расшифровка для выгрузки из библиотеки, где встреча не открыта: читается свежей. */
export const transcriptForExport = (id: string) => everyLine(id);

/** Реплики сервера как их показывает страница: секунды от начала и подпись голоса на языке человека. */
export function transcriptLinesOf(
  lines: readonly TranscriptLineOut[],
  speakers: readonly MeetingSpeaker[],
  name: (voice: Voice) => string,
): TranscriptLine[] {
  return lines.map((line) => ({
    speaker: name(voiceOf(line.speaker, speakers)),
    at: Math.floor(line.start_ms / 1000),
    duration: line.duration_ms / 1000,
    text: line.text,
  }));
}
