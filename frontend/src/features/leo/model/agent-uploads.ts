import { browserUploadPorts, runLimited, uploadFile } from "@/lib/uploads/upload-file";

/*
 * Файлы вопроса Leo — загрузки `leo_attachment` прямо в бакет дома (FL-D1, шаг 12 агента): ход называет их id,
 * сервер берёт их в транзакции хода. Два файла грузятся сразу, порядок ответа — порядок файлов.
 */

const PORTS = browserUploadPorts("leo_attachment");
const AT_ONCE = 2;

/** Id готовых загрузок файлов в их порядке; первый же сбой роняет всё — вопрос без части файлов не уходит. */
export async function uploadedAttachments(files: readonly File[]): Promise<string[]> {
  const ids: string[] = Array.from({ length: files.length }, () => "");
  await runLimited(
    files.map((_, index) => index),
    AT_ONCE,
    async (index) => {
      ids[index] = await uploadFile(files[index], PORTS, () => undefined);
    },
  );
  return ids;
}
