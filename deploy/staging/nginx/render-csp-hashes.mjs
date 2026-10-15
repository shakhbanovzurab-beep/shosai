// Хеши встроенных скриптов кабинета (dist/csp-hashes.json, ADR 0019) — в переменную NGINX для CSP.
// Запускается при сборке образа edge: node render-csp-hashes.mjs <csp-hashes.json> <выходной .conf>.
import { readFileSync, writeFileSync } from "node:fs";

const [source, target] = process.argv.slice(2);
const hashes = JSON.parse(readFileSync(source, "utf8"))["script-src"];
if (!Array.isArray(hashes) || hashes.length === 0 || !hashes.every((hash) => /^'sha256-[A-Za-z0-9+/=]+'$/.test(hash))) {
  throw new Error(`${source}: script-src must list 'sha256-…' hashes`);
}
writeFileSync(target, `set $shosai_csp_script_hashes "${hashes.join(" ")}";\n`);
