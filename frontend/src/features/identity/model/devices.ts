import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { type Device, endDevice, listDevices, signOutOtherDevices } from "../api/account-data-api";

const DEVICES_KEY = ["identity", "devices"] as const;

/** Устройства с открытой сессией, постранично; текущее отмечено сервером. */
export function useDevices() {
  const query = useInfiniteQuery({
    queryKey: DEVICES_KEY,
    queryFn: ({ pageParam }) => listDevices(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
  });
  const devices: Device[] = query.data?.pages.flatMap((page) => page.items) ?? [];
  return { ...query, devices };
}

/** Закрыть сессию одного устройства или всех, кроме этого; список обновляется после ответа. */
export function useDeviceSignOut() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: DEVICES_KEY });
  const one = useMutation({ mutationFn: endDevice, onSettled: refresh });
  const others = useMutation({ mutationFn: signOutOtherDevices, onSettled: refresh });
  return { one, others };
}
