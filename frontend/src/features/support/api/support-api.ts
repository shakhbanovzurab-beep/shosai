import { apiRequest, jsonBody } from "@/lib/api/request";

import type { TicketCategory, TicketDetail, TicketsResponse, UpdateTicketRequest } from "../domain/contract";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/support${path}`, init);
const ticketPath = (id: string) => `/tickets/${encodeURIComponent(id)}`;

const messageForm = (body: string, files: File[]) => {
  const form = new FormData();
  form.append("body", body);
  for (const file of files) form.append("files", file);
  return form;
};

export const supportApi = {
  list: () => request<TicketsResponse>("/tickets"),
  get: (id: string) => request<TicketDetail>(ticketPath(id)),
  create: (subject: string, category: TicketCategory, body: string, files: File[]) => {
    const form = messageForm(body, files);
    form.append("subject", subject);
    form.append("category", category);
    return request<TicketDetail>("/tickets", { method: "POST", body: form });
  },
  reply: (id: string, body: string, files: File[]) =>
    request<TicketDetail>(`${ticketPath(id)}/messages`, { method: "POST", body: messageForm(body, files) }),
  update: (id: string, patch: UpdateTicketRequest) => request<TicketDetail>(ticketPath(id), jsonBody("PATCH", patch)),
};
