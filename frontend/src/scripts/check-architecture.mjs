// Checks the import rules from docs/architecture.md and the 200-line limit. Run: npm run lint:architecture
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "../..");
const MAX_LINES = 200;
const LAYERS = ["domain", "data", "api", "model", "ui", "server"];
/** For each layer, the layers of the same slice it may import. */
const INNER = {
  domain: ["domain"],
  data: ["domain", "data"],
  api: ["domain", "api"],
  model: ["domain", "data", "api", "model"],
  ui: ["domain", "data", "model", "ui"],
  server: ["domain", "data", "server"],
  index: ["domain", "data", "model", "ui"],
  "server-entry": ["domain", "server"],
};
/** Packages that tie code to React, Next.js, the UI or a store. */
const FRAMEWORK = /^(react|react-dom|next|zustand|sonner|lucide-react|framer-motion|recharts|radix-ui|cmdk|vaul)(\/|$)/;
const PURE_BANNED = /^@\/(components|hooks|server)\/|^@\/lib\/(api-client|polling-resource|copy-text|.*\.client)$/;
// Vendored code, and the message-catalog type declarations next-intl generates (src/i18n/messages/en/*.d.json.ts).
const LENGTH_EXEMPT = [/^src\/components\/(ui|calendar)\//, /^src\/styles\/flag-icons\//, /\.d\.json\.ts$/];
const SOURCE = /\.(ts|tsx|mjs|css)$/;
const IMPORT =
  /(?:^|[\s;{}])(?:import|export)\s[^'"`;]*?from\s*["']([^"']+)["']|import\s*\(\s*["']([^"']+)["']\s*\)|^\s*import\s*["']([^"']+)["']/gm;

/** Server Actions are RPC endpoints, so client layers of the same slice may call them. */
const isServerActions = (path) =>
  ["", ".ts", ".tsx"].some((extension) => {
    try {
      return readFileSync(join(ROOT, path + extension), "utf8")
        .trimStart()
        .startsWith('"use server"');
    } catch {
      return false;
    }
  });

const files = [];
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else if (SOURCE.test(name)) files.push(relative(ROOT, path));
  }
};
walk(join(ROOT, "src"));

/** Where a path inside src/ sits: a slice and its layer or entry, the routing layer, or the shared layer. */
function locate(path) {
  const parts = path.replace(/\.(ts|tsx|mjs|json|css)$/, "").split("/");
  if (parts[1] === "app") return { kind: "app" };
  if (parts[1] === "scripts") return { kind: "scripts" };
  if (parts[1] !== "features") return { kind: "shared" };
  const [slice, entry] = [parts[2], parts[3]];
  if (entry === undefined || entry === "index") return { kind: "feature", slice, layer: "index", depth: parts.length };
  if (entry === "server" && parts.length === 4) return { kind: "feature", slice, layer: "server-entry", depth: 4 };
  return { kind: "feature", slice, layer: LAYERS.includes(entry) ? entry : null, depth: parts.length };
}

const problems = [];
const sliceEdges = new Map();
const report = (file, message) => problems.push(`${file}: ${message}`);

function checkImport(file, from, spec) {
  if (spec.startsWith("@/app/")) return report(file, `imports a route module (${spec}); routes are not importable`);
  const internal = spec.startsWith("@/") || spec.startsWith(".");
  const targetPath = spec.startsWith("@/")
    ? `src/${spec.slice(2)}`
    : relative(ROOT, resolve(ROOT, dirname(file), spec));
  const target = internal ? locate(targetPath) : null;
  const pureLayer = from.kind === "feature" && ["domain", "data", "api"].includes(from.layer);

  if (pureLayer && !internal && FRAMEWORK.test(spec)) return report(file, `${from.layer} must not depend on "${spec}"`);
  if (pureLayer && PURE_BANNED.test(spec) && !(from.layer === "api" && spec === "@/lib/api-client"))
    return report(file, `${from.layer} must not depend on "${spec}"`);
  if (!target) return;

  if (from.kind === "shared" && target.kind === "feature")
    return report(file, `shared code must not import features (${spec})`);
  if (from.kind === "feature" && from.layer === null) return report(file, "is outside the slice layers");
  if (target.kind !== "feature") {
    const clientLayer = from.kind === "feature" && !["server", "server-entry"].includes(from.layer);
    if (clientLayer && spec.startsWith("@/server/"))
      report(file, `client code must not import server infrastructure (${spec})`);
    if (
      from.kind === "feature" &&
      ["model", "domain", "data", "api"].includes(from.layer) &&
      spec.startsWith("@/components/")
    )
      report(file, `${from.layer} must not import UI components (${spec})`);
    return;
  }

  if (from.kind !== "feature" || from.slice !== target.slice) {
    const isEntry = target.layer === "index" || target.layer === "server-entry";
    if (!isEntry || target.depth > 4) return report(file, `reaches into ${target.slice}'s internals (${spec})`);
    if (from.kind === "feature") {
      const serverSide = from.layer === "server" || from.layer === "server-entry";
      if (from.layer === "domain" || from.layer === "data" || from.layer === "api")
        return report(file, `${from.layer} must not import other slices (${spec})`);
      if (serverSide !== (target.layer === "server-entry"))
        return report(
          file,
          `${serverSide ? "server" : "client"} code must import ${target.slice}'s ${serverSide ? "server.ts" : "index.ts"} (${spec})`,
        );
      if (!sliceEdges.has(from.slice)) sliceEdges.set(from.slice, new Set());
      sliceEdges.get(from.slice).add(target.slice);
    }
    return;
  }

  if (target.layer === "index" || target.layer === "server-entry")
    return report(file, `imports its own slice's public API (${spec}); use a relative import`);
  const callsAction = ["model", "ui"].includes(from.layer) && target.layer === "server" && isServerActions(targetPath);
  if (!INNER[from.layer].includes(target.layer) && !callsAction)
    report(file, `${from.layer} must not import ${target.layer} (${spec})`);
}

for (const file of files) {
  const source = readFileSync(join(ROOT, file), "utf8");
  const lines = source.split("\n").length - (source.endsWith("\n") ? 1 : 0);
  if (lines > MAX_LINES && !LENGTH_EXEMPT.some((pattern) => pattern.test(file)))
    report(file, `${lines} lines, over the ${MAX_LINES}-line limit`);
  if (file.endsWith(".css") || file.startsWith("src/scripts/")) continue;
  const from = locate(file);
  for (const match of source.matchAll(IMPORT)) checkImport(file, from, match[1] ?? match[2] ?? match[3]);
}

// Slices may depend on each other only one way.
const visit = (slice, trail) => {
  if (trail.includes(slice))
    return problems.push(`slice cycle: ${[...trail.slice(trail.indexOf(slice)), slice].join(" → ")}`);
  for (const next of sliceEdges.get(slice) ?? []) visit(next, [...trail, slice]);
};
for (const slice of sliceEdges.keys()) visit(slice, []);

const unique = [...new Set(problems)];
for (const problem of unique) console.error(problem);
console.log(unique.length === 0 ? "Architecture: no violations." : `Architecture: ${unique.length} violation(s).`);
process.exitCode = unique.length === 0 ? 0 : 1;
