const describedBy = (id: string, description: unknown, error: unknown) =>
  [description ? `${id}-description` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;

/** Props that link a control to its FormField hint and error. */
export const fieldAria = (id: string, description: unknown, error: unknown) => ({
  id,
  "aria-invalid": error ? true : undefined,
  "aria-describedby": describedBy(id, description, error),
});
