// PreToolUse (Edit|Write|MultiEdit): before Claude touches React code, require the React skills
// to be loaded in this session. PostToolUse: remember that React code changed so the Stop hook
// runs React Doctor.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { extname, isAbsolute, join, relative } from "node:path";

const REQUIRED_SKILLS = [
  "vercel-react-best-practices",
  "vercel-composition-patterns",
  "vercel-react-view-transitions",
  "web-design-guidelines",
];
const REACT_EXTENSIONS = new Set([".tsx", ".jsx"]);
const SCRIPT_EXTENSIONS = new Set([".ts", ".js", ".mts", ".mjs"]);
const REACT_IMPORT_PATTERN = /from\s+["'](?:react|react-dom|next)(?:\/[^"']*)?["']|\buse[A-Z]\w*\(/;

const readStdin = () => {
  try {
    return JSON.parse(readFileSync(0, "utf8") || "{}");
  } catch {
    return {};
  }
};

const markerPath = (sessionId) => join(tmpdir(), "claude-react-doctor", `${sessionId || "unknown"}.json`);

const isReactFile = (filePath, toolInput) => {
  const projectRoot = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const relativePath = isAbsolute(filePath) ? relative(projectRoot, filePath) : filePath;
  if (relativePath.startsWith("..") || /(^|\/)(node_modules|\.next|\.claude)\//.test(relativePath)) return false;

  const extension = extname(filePath);
  if (REACT_EXTENSIONS.has(extension)) return true;
  if (!SCRIPT_EXTENSIONS.has(extension)) return false;

  let source = [toolInput.content, toolInput.new_string, ...(toolInput.edits ?? []).map((edit) => edit.new_string)]
    .filter(Boolean)
    .join("\n");
  try {
    source += readFileSync(filePath, "utf8");
  } catch {
    // New file: only the content being written is known.
  }
  return REACT_IMPORT_PATTERN.test(source);
};

const findLoadedSkills = (transcriptPath) => {
  const loaded = new Set();
  let transcript = "";
  try {
    transcript = readFileSync(transcriptPath, "utf8");
  } catch {
    return loaded;
  }
  for (const line of transcript.split("\n")) {
    if (!line.includes("Skill") && !line.includes("command-name")) continue;
    let entry;
    try {
      entry = JSON.parse(line);
    } catch {
      continue;
    }
    const content = entry.message?.content;
    if (Array.isArray(content)) {
      for (const block of content) {
        if (block?.type === "tool_use" && block.name === "Skill" && typeof block.input?.skill === "string") {
          loaded.add(block.input.skill);
        }
      }
    }
    // Skills the user invoked as slash commands.
    for (const match of line.matchAll(/<command-name>\/?([\w:-]+)<\/command-name>/g)) loaded.add(match[1]);
  }
  return loaded;
};

const main = () => {
  const input = readStdin();
  const toolInput = input.tool_input ?? {};
  const filePath = toolInput.file_path;
  if (typeof filePath !== "string" || !isReactFile(filePath, toolInput)) return;

  if (input.hook_event_name === "PostToolUse") {
    const path = markerPath(input.session_id);
    mkdirSync(join(tmpdir(), "claude-react-doctor"), { recursive: true });
    let marker = { blocks: 0 };
    try {
      marker = JSON.parse(readFileSync(path, "utf8"));
    } catch {
      // No marker yet: this is the first React edit of the session.
    }
    writeFileSync(path, JSON.stringify({ ...marker, pending: true }));
    return;
  }

  const loaded = findLoadedSkills(input.transcript_path);
  const missing = REQUIRED_SKILLS.filter((skill) => !loaded.has(skill));
  if (missing.length === 0) return;

  console.log(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: `This edit touches React code (${filePath}). Before writing React in this project, load these skills with the Skill tool and follow their rules: ${missing.join(", ")}. Then retry the edit.`,
      },
    }),
  );
};

main();
