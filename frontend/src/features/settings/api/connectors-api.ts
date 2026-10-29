import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type {
  Connector,
  ConnectorCredentials,
  ConnectorsResponse,
  DrivePickerSetup,
} from "../domain/connectors-contract";

/* Коннекторы человека на `/v1/connectors*` (план connectors §3.7). */

const app = (id: string) => ({ params: { path: { app: id } } });

export const connectorsApi = {
  list: (): Promise<ConnectorsResponse> => dataOf(apiClient.GET("/v1/connectors")),
  /** Страница согласия провайдера; ответ ставит cookie-привязку, без которой обратный адрес не завершит поток. */
  authorize: async (id: string): Promise<string> =>
    (await dataOf(apiClient.POST("/v1/connectors/{app}/authorize", { ...app(id), body: { return: "popup" } })))
      .authorize_url,
  connectWithCredentials: (id: string, body: ConnectorCredentials): Promise<Connector> =>
    dataOf(apiClient.POST("/v1/connectors/{app}/credentials", { ...app(id), body })),
  disconnect: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/connectors/{app}", app(id))),
  /** Настройка Google Picker для подключённого Диска; токена в ней нет. */
  drivePicker: (): Promise<DrivePickerSetup> => dataOf(apiClient.GET("/v1/connectors/google_drive/picker")),
};
