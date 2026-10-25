import { refreshDomains } from "@/lib/resource-domains";

import type { NumberedEvent } from "../domain/run-events";
import { proposalArrived, receiveCard } from "./proposal-store";

/*
 * Что события карточек меняют вне ответа: новая карточка попадает в «Нужны вы», итог карточки виден везде, где
 * она показана, а данные, которые изменило действие (`invalidates`), перечитываются на показанных экранах.
 */
export function onCardEvent(event: NumberedEvent) {
  if (event.kind === "action.proposed") proposalArrived();
  if (event.kind !== "action.updated") return;
  receiveCard(event.data.action);
  if (event.data.invalidates) refreshDomains(event.data.invalidates);
}
