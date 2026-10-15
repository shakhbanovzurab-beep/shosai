import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

export type DevicePage = components["schemas"]["Page_DeviceView_"];
export type Device = components["schemas"]["DeviceView"];
export type ExportJob = components["schemas"]["ExportJob"];
export type DeletionScheduled = components["schemas"]["DeletionScheduled"];

/** Устройства с открытой сессией, новые сверху; `cursor` — следующая страница. */
export function listDevices(cursor: string | null): Promise<DevicePage> {
  return dataOf(apiClient.GET("/v1/me/devices", { params: { query: cursor ? { cursor } : {} } }));
}

/** Закрыть сессию одного устройства. */
export async function endDevice(deviceId: string): Promise<void> {
  await dataOf(apiClient.DELETE("/v1/me/devices/{device_id}", { params: { path: { device_id: deviceId } } }));
}

/** Закрыть сессии всех устройств, кроме этого; ответ — сколько закрыто. */
export async function signOutOtherDevices(): Promise<number> {
  return (await dataOf(apiClient.POST("/v1/me/devices/sign-out-others"))).ended;
}

/** Попросить выгрузку всех данных; архив соберётся в фоне и придёт письмом. */
export function requestExport(): Promise<ExportJob> {
  return dataOf(apiClient.POST("/v1/me/exports"));
}

/** Последняя выгрузка; 404 — выгрузок ещё не было. */
export function latestExport(): Promise<ExportJob> {
  return dataOf(apiClient.GET("/v1/me/exports/latest"));
}

/** Назначить удаление аккаунта через 7 дней; адрес набран заново для подтверждения. */
export function scheduleDeletion(confirmEmail: string): Promise<DeletionScheduled> {
  return dataOf(apiClient.POST("/v1/me/deletion", { body: { confirm_email: confirmEmail } }));
}
