import { type LoaderFunctionArgs, redirect } from "react-router";

import { safeNext } from "@/features/identity/domain/next-path";
import { startSession } from "@/features/identity/model/session";

/** Регистрация и забытый пароль — для того, кто не вошёл; вошедший возвращается туда, куда шёл. */
export async function loader({ request }: LoaderFunctionArgs) {
  const me = await startSession();
  if (me !== null) throw redirect(safeNext(new URL(request.url).searchParams.get("next")));
  return null;
}
