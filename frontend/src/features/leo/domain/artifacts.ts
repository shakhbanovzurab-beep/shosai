/*
 * Артефакты ответа Leo (Leo §13.2, событие `artifact`): ссылка на результат, который читают отдельно.
 * `chat_digest` — дайджест командного чата (CF-D11, требование AG-R1 плана agent): поток несёт только ссылку,
 * сам дайджест хранит слайс chats 30 дней и стирает вместе с чатом.
 * `chart` — график оператору в админ-панели (agent шаг 16): строки посчитаны инструментом, кабинет только рисует.
 * `image` — картинка, нарисованная оператору (agent шаг 16b2): объект платформы по ссылке, с размерами в пикселях.
 */

export type ChatDigestArtifact = {
  kind: "chat_digest";
  /** Ид дайджеста. */
  ref: string;
  /** Подпись для тех, кто карточку не видит. */
  alt: string;
  workspace_id: string;
  chat_id: string;
};

export type ChartSeries = { key: string; label: string };

export type ChartSpec = {
  shape: "bar" | "line";
  /** Столбец строк по оси x. */
  x: string;
  stacked: boolean;
  series: ChartSeries[];
  rows: Record<string, string | number | null>[];
};

export type ChartArtifact = {
  kind: "chart";
  /** `chart:<id отчёта>`. */
  ref: string;
  /** Заголовок графика. */
  alt: string;
  spec: ChartSpec;
};

export type ImageArtifact = {
  kind: "image";
  /** Ид картинки. */
  ref: string;
  /** Подпись картинки. */
  alt: string;
  width: number;
  height: number;
};

export type LeoArtifact = ChatDigestArtifact | ChartArtifact | ImageArtifact;

/** Картинку оператора отдаёт API по cookie админа: переадресацией на короткую ссылку бакета. */
export function operatorImageUrl(ref: string): string {
  return `/v1/admin/agent/images/${encodeURIComponent(ref)}`;
}
