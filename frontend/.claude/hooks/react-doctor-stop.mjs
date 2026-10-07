// Stop: if React code changed during this session, run a full React Doctor scan and keep Claude
// working until it reports no issues (score 100/100).
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Stop retrying after this many consecutive blocked stops so a stubborn finding can't loop forever.
const MAX_BLOCKS = 3;
const SPAWN_MAX_BUFFER_BYTES = 16 * 1024 * 1024;

// Same marker as react-skills-gate.mjs writes after React edits.
const markerPath = (sessionId) => join(tmpdir(), "claude-react-doctor", `${sessionId || "unknown"}.json`);

const readStdin = () => {
  try {
    return JSON.parse(readFileSync(0, "utf8") || "{}");
  } catch {
    return {};
  }
};

const main = () => {
  const input = readStdin();
  const path = markerPath(input.session_id);
  if (!existsSync(path)) return;

  let marker;
  try {
    marker = JSON.parse(readFileSync(path, "utf8"));
  } catch {
    marker = { pending: true, blocks: 0 };
  }
  if (!marker.pending) return;

  const projectRoot = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const localBin = `${projectRoot}/node_modules/.bin/react-doctor`;
  const command = existsSync(localBin) ? `"${localBin}"` : "npx --yes react-doctor@latest";
  const result = spawnSync(`${command} --verbose --blocking warning --no-score --no-color`, {
    cwd: projectRoot,
    encoding: "utf8",
    shell: true,
    maxBuffer: SPAWN_MAX_BUFFER_BYTES,
  });
  const output = `${result.stdout ?? ""}${result.stderr ?? ""}`.trim();

  if (result.status === 0) {
    unlinkSync(path);
    console.log(JSON.stringify({ systemMessage: "React Doctor: no issues found (100/100)." }));
    return;
  }

  const blocks = (marker.blocks ?? 0) + 1;
  if (blocks > MAX_BLOCKS) {
    unlinkSync(path);
    console.log(
      JSON.stringify({
        systemMessage: `React Doctor still reports issues after ${MAX_BLOCKS} fix attempts. Run \`npm run doctor\` to review them.`,
      }),
    );
    return;
  }
  writeFileSync(path, JSON.stringify({ pending: true, blocks }));

  const report = output.slice(output.indexOf("React Doctor —") >= 0 ? output.indexOf("React Doctor —") : 0);
  console.log(
    JSON.stringify({
      decision: "block",
      reason: `React Doctor found issues; the project must stay at 100/100. Fix the root cause of each finding (use the react-doctor skill; never silence a rule without evidence it is a false positive), then finish again.\n\n${report}`,
    }),
  );
};

main();
