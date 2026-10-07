/** The message of a thrown Error, for toasts and inline errors; undefined for anything else. */
export const errorMessage = (error: unknown) => (error instanceof Error ? error.message : undefined);
