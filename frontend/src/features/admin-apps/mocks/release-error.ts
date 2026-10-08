/** Сбой с HTTP-статусом, которым должен ответить маршрут. */
export class ReleaseError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
