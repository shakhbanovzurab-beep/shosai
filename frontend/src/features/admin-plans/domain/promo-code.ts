/** No 0/O, 1/I/L: codes are read aloud and retyped from screenshots. */
const ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";

/** A random upper-case code of `length` characters from the unambiguous alphabet. */
export function randomCode(length: number) {
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(bytes, (byte) => ALPHABET[byte % ALPHABET.length]).join("");
}
