/**
 * Подсказки к новому паролю. Сервер требует только длину (8–256 символов); остальные правила советуют, как
 * сделать пароль крепче, и ничего не запрещают — иначе форма отвергала бы то, что принимает сервер.
 */
export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 256;

export const PASSWORD_RULES = ["length", "case", "number", "symbol"] as const;

export type PasswordRule = (typeof PASSWORD_RULES)[number];

// Буквы и символы — через классы Юникода: перечень ASCII отверг бы «§» или «ß» другой раскладки.
const MET: Record<PasswordRule, (password: string) => boolean> = {
  length: (password) => password.length >= PASSWORD_MIN_LENGTH,
  case: (password) => /\p{Ll}/u.test(password) && /\p{Lu}/u.test(password),
  number: (password) => /\p{N}/u.test(password),
  symbol: (password) => /[^\p{L}\p{N}\s]/u.test(password),
};

export type PasswordStrength = "weak" | "fair" | "good" | "strong";

const STRENGTH_BY_SCORE: readonly PasswordStrength[] = ["weak", "weak", "fair", "good", "strong"];

export interface PasswordCheck {
  strength: PasswordStrength;
  /** Сколько правил выполнено, 0…4. */
  score: number;
  unmet: PasswordRule[];
}

export function checkPassword(password: string): PasswordCheck {
  const unmet = PASSWORD_RULES.filter((rule) => !MET[rule](password));
  const score = PASSWORD_RULES.length - unmet.length;
  return { strength: STRENGTH_BY_SCORE[score] ?? "weak", score, unmet };
}

/** Пароль, который примет сервер. */
export function acceptablePassword(password: string): boolean {
  return password.length >= PASSWORD_MIN_LENGTH && password.length <= PASSWORD_MAX_LENGTH;
}
