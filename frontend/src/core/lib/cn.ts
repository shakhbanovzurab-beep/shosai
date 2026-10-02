import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Склейка классов: условные — через clsx, конфликты Tailwind разрешает
 * twMerge, и последний выигрывает: `cn("p-2", "p-4")` даёт `p-4`.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
