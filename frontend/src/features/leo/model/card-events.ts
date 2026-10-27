import type { NumberedEvent } from "../domain/run-events";
import { proposalArrived, receiveCard } from "./proposal-store";

/*
 * Что события карточек меняют вне ответа: новая карточка попадает в «Нужны вы», итог карточки виден везде, где
 * она показана, а данные, которые изменило действие (`invalidates`), перечитываются на показанных экранах — один
 * раз, сколько бы раз итог ни пришёл. `invalidates` события — для карточек сервера, который ещё не кладёт его в
 * саму карточку.
 */
export function onCardEvent(event: NumberedEvent) {
  if (event.kind === "action.proposed") proposalArrived();
  if (event.kind !== "action.updated") return;
  const { action, invalidates } = event.data;
  receiveCard(action.invalidates === undefined && invalidates ? { ...action, invalidates } : action);
}
