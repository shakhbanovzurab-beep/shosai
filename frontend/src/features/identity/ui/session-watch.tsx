import { useEffect } from "react";

import { usePathname, useRouter, useSearchParams } from "@/lib/navigation";

import { loginPathFor } from "../domain/next-path";
import { useSession } from "../model/session-store";

/** На странице панели: если сессия кончилась — здесь или в другой вкладке, — ведёт на вход и обратно сюда. */
export function SessionWatch() {
  const { status } = useSession();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const router = useRouter();

  useEffect(() => {
    if (status !== "signed-out") return;
    router.replace(loginPathFor(search ? `${pathname}?${search}` : pathname));
  }, [status, pathname, search, router]);

  return null;
}
