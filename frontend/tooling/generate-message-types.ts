// Запуск перед tsc: node tooling/generate-message-types.ts

import { writeMessageTypes } from "./message-types.ts";
import { fileURLToPath } from "node:url";

const englishDir = fileURLToPath(new URL("../src/i18n/messages/en", import.meta.url));
writeMessageTypes(englishDir);
