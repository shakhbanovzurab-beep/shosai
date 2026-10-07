/*
 * Global shortcuts of the Whisperer desktop app. They are edited in Settings › Hotkeys, saved with the
 * user's settings and read by the desktop app, where they work even when it is in the background.
 *
 * A combo is "Mod+Alt+Z": modifiers in the order Mod, Alt, Shift, then one key. "Mod" is ⌘ on macOS
 * and Ctrl on Windows. Keys are physical keys (`KeyboardEvent.code`), so a shortcut is the same with
 * any keyboard layout, Cyrillic included.
 */

export const HOTKEY_IDS = [
  "open_app",
  "toggle_recording",
  "toggle_overlay",
  "open_settings",
  "collapse_overlay",
  "close_app",
  "live_translation",
  "prompter",
] as const;
export type HotkeyId = (typeof HOTKEY_IDS)[number];

/** The user's changes only: a combo, or null for "off". A missing id uses the default. */
export type HotkeyBindings = Partial<Record<HotkeyId, string | null>>;

/** Each command's default combo, in the order Settings › Hotkeys lists them; the UI words the commands. */
export const HOTKEY_COMMANDS: readonly { id: HotkeyId; default: string }[] = [
  { id: "open_app", default: "Mod+Alt+Z" },
  { id: "toggle_recording", default: "Mod+Alt+X" },
  { id: "toggle_overlay", default: "Mod+Alt+C" },
  { id: "open_settings", default: "Mod+Alt+V" },
  { id: "collapse_overlay", default: "Mod+Alt+B" },
  { id: "close_app", default: "Mod+Alt+Space" },
  { id: "live_translation", default: "Mod+Alt+P" },
  { id: "prompter", default: "Mod+Alt+T" },
];

export const isHotkeyId = (id: string): id is HotkeyId => (HOTKEY_IDS as readonly string[]).includes(id);

/** System shortcuts the desktop app can't take over. */
const RESERVED = new Set(["Mod+Space", "Mod+Tab", "Mod+Q", "Mod+W", "Mod+Alt+Escape", "Mod+Shift+Tab"]);

const NAMED_KEYS = [
  "Comma",
  "Period",
  "Slash",
  "Semicolon",
  "Quote",
  "BracketLeft",
  "BracketRight",
  "Backslash",
  "Minus",
  "Equal",
  "Backquote",
  "Enter",
  "Space",
];
const KEY = `(?:[A-Z]|[0-9]|F(?:[1-9]|1[0-2])|${NAMED_KEYS.join("|")})`;
const KEY_PATTERN = new RegExp(`^${KEY}$`);
const COMBO_PATTERN = new RegExp(`^(?:Mod\\+)?(?:Alt\\+)?(?:Shift\\+)?${KEY}$`);

export const isValidCombo = (combo: string) => COMBO_PATTERN.test(combo);

/** The key part of a combo from `KeyboardEvent.code`: KeyZ → "Z", Digit1 → "1", Space → "Space". */
function keyOf(code: string) {
  if (code.startsWith("Key")) return code.slice(3);
  if (code.startsWith("Digit")) return code.slice(5);
  return KEY_PATTERN.test(code) ? code : null;
}

type KeyEventLike = Pick<KeyboardEvent, "code" | "metaKey" | "ctrlKey" | "altKey" | "shiftKey">;

/** The combo a key press makes, or null for a lone modifier or an unsupported key. */
export function comboFromEvent(event: KeyEventLike, isMac: boolean) {
  const key = keyOf(event.code);
  if (!key) return null;
  // Ctrl on a Mac and the Windows key elsewhere aren't part of any combo here.
  if (isMac ? event.ctrlKey : event.metaKey) return null;
  const mod = isMac ? event.metaKey : event.ctrlKey;
  return [mod && "Mod", event.altKey && "Alt", event.shiftKey && "Shift", key].filter(Boolean).join("+");
}

/** Every command's combo: the user's choice where there is one, otherwise the default. */
export function effectiveBindings(saved: HotkeyBindings): Record<HotkeyId, string | null> {
  return Object.fromEntries(
    HOTKEY_COMMANDS.map((c) => [c.id, c.id in saved ? (saved[c.id] ?? null) : c.default]),
  ) as Record<HotkeyId, string | null>;
}

/**
 * Why a combo can't be used, as a code the UI and the API word in the interface language: it lacks ⌘/Ctrl
 * or ⌥/Alt (a global shortcut needs one), the system keeps it, or another command (`owner`) has it.
 */
export type ComboProblem = { code: "needsModifier" } | { code: "reserved" } | { code: "taken"; owner: HotkeyId };

/** Why a combo can't be used, or null when it can. */
export function comboProblem(
  combo: string,
  id: HotkeyId,
  bindings: Record<HotkeyId, string | null>,
): ComboProblem | null {
  if (!combo.startsWith("Mod+") && !combo.startsWith("Alt+")) return { code: "needsModifier" };
  if (RESERVED.has(combo)) return { code: "reserved" };
  const owner = HOTKEY_COMMANDS.find((c) => c.id !== id && bindings[c.id] === combo);
  return owner ? { code: "taken", owner: owner.id } : null;
}

const KEY_LABELS: Record<string, string> = {
  Comma: ",",
  Period: ".",
  Slash: "/",
  Semicolon: ";",
  Quote: "'",
  BracketLeft: "[",
  BracketRight: "]",
  Backslash: "\\",
  Minus: "-",
  Equal: "=",
  Backquote: "`",
};

/** The keys to draw: ["⌥", "⌘", "Z"] on a Mac (its own order: ⌥ ⇧ ⌘), ["Ctrl", "Alt", "Z"] elsewhere. */
export function comboKeys(combo: string, isMac: boolean) {
  const parts = combo.split("+");
  const key = parts.at(-1) ?? "";
  const has = (modifier: string) => parts.includes(modifier);
  const modifiers = isMac
    ? [has("Alt") && "⌥", has("Shift") && "⇧", has("Mod") && "⌘"]
    : [has("Mod") && "Ctrl", has("Alt") && "Alt", has("Shift") && "Shift"];
  return [...modifiers.filter((m): m is string => Boolean(m)), KEY_LABELS[key] ?? key];
}
