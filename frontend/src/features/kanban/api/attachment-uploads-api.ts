import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import { browserUploadPorts, type UploadPorts } from "@/lib/uploads/upload-file";

/*
 * Загрузка вложения задачи — общая загрузка кабинета (`/v1/me/uploads*`) с назначением `task_attachment` и, у
 * задачи пространства, его id: байты ложатся в место владельца задачи (KG-D3); части, сборка и отмена — те же,
 * что у всех.
 */

export function taskAttachmentPorts(workspaceId: string | null): UploadPorts {
  return {
    ...browserUploadPorts("task_attachment"),
    create: (file) =>
      dataOf(
        apiClient.POST("/v1/me/uploads", {
          body: {
            purpose: "task_attachment",
            filename: file.name,
            content_type: file.type || "application/octet-stream",
            size_bytes: file.size,
            workspace_id: workspaceId,
          },
        }),
      ),
  };
}
