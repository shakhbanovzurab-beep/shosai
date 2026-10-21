import { apiRequest, jsonBody } from "@/lib/api/request";
import { browserUploadPorts, type UploadPorts } from "@/lib/uploads/upload-file";
import type { UploadAnswer } from "@/lib/uploads/uploads-api";

/*
 * Загрузка вложения задачи — общая загрузка кабинета (`/v1/me/uploads*`) с назначением `task_attachment` и, у
 * задачи пространства, его id: байты ложатся в место владельца задачи (KG-D3). Схема API этого назначения ещё не
 * знает (его добавляет требование tasks к files, план files §3.2), поэтому создание загрузки идёт мимо
 * сгенерированного клиента; части, сборка и отмена — те же, что у всех.
 */

export function taskAttachmentPorts(workspaceId: string | null): UploadPorts {
  return {
    ...browserUploadPorts("file_manager"),
    create: (file) =>
      apiRequest<UploadAnswer>(
        "/v1/me/uploads",
        jsonBody("POST", {
          purpose: "task_attachment",
          filename: file.name,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
          ...(workspaceId ? { workspace_id: workspaceId } : {}),
        }),
      ),
  };
}
