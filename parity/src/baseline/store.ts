// Снимки эталона в S3 (решение владельца, план D2 §5): бакет из PARITY_S3_*,
// только префикс parity-baseline/, ключ — хеш содержимого.
//
// Бакет боевой, поэтому стенд не читает, не перечисляет и не удаляет ничего вне
// своего префикса: каждый ключ проверяется до запроса. Ключ по хешу означает,
// что загрузка никогда не перезаписывает чужой или прежний снимок.

import { GetObjectCommand, HeadObjectCommand, PutObjectCommand, S3Client, S3ServiceException } from "@aws-sdk/client-s3";

export const BASELINE_PREFIX = "parity-baseline/";

export function objectKey(sha: string): string {
  if (!/^[0-9a-f]{64}$/.test(sha)) throw new Error(`Не хеш SHA-256: ${sha}`);
  return `${BASELINE_PREFIX}sha256/${sha}.png`;
}

function guarded(key: string): string {
  if (!key.startsWith(BASELINE_PREFIX)) throw new Error(`Ключ вне ${BASELINE_PREFIX}: ${key}`);
  return key;
}

export interface BaselineStore {
  exists(key: string): Promise<boolean>;
  put(key: string, body: Buffer): Promise<void>;
  get(key: string): Promise<Buffer>;
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value === "") {
    throw new Error(`Не задана ${name}: хранилище эталона настраивается переменными PARITY_S3_* (parity/README.md)`);
  }
  return value;
}

export function s3StoreFromEnv(): BaselineStore {
  const bucket = requireEnv("PARITY_S3_BUCKET");
  const client = new S3Client({
    endpoint: requireEnv("PARITY_S3_ENDPOINT"),
    region: requireEnv("PARITY_S3_REGION"),
    credentials: {
      accessKeyId: requireEnv("PARITY_S3_ACCESS_KEY_ID"),
      secretAccessKey: requireEnv("PARITY_S3_SECRET_ACCESS_KEY"),
    },
    // Как у черновика (services/storage/s3_client.py): адресация по пути, подпись v4.
    forcePathStyle: true,
    // S3-совместимые хранилища не обязаны знать новые контрольные суммы AWS.
    requestChecksumCalculation: "WHEN_REQUIRED",
    responseChecksumValidation: "WHEN_REQUIRED",
  });
  return {
    async exists(key) {
      try {
        await client.send(new HeadObjectCommand({ Bucket: bucket, Key: guarded(key) }));
        return true;
      } catch (error) {
        if (error instanceof S3ServiceException && error.$metadata.httpStatusCode === 404) return false;
        throw error;
      }
    },
    async put(key, body) {
      await client.send(
        new PutObjectCommand({ Bucket: bucket, Key: guarded(key), Body: body, ContentType: "image/png" }),
      );
    },
    async get(key) {
      const response = await client.send(new GetObjectCommand({ Bucket: bucket, Key: guarded(key) }));
      if (response.Body === undefined) throw new Error(`Пустой ответ S3 для ${key}`);
      return Buffer.from(await response.Body.transformToByteArray());
    },
  };
}
