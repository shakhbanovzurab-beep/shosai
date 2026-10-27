"use client";

import { toast } from "sonner";

import { digestProposalDecided } from "@/features/chats/model/digests";
import { apiErrorDescription } from "@/lib/api/error-description";
import { ApiError } from "@/lib/api/errors";

import { proposalsApi } from "../api/proposals-api";
import type { DecidedProposal, LeoProposal } from "../domain/proposals";
import { markBusy, proposalArrived, receiveCard } from "./proposal-store";
import { followRun } from "./run-follower";

/*
 * Решение по карточке — из разговора или из «Нужны вы». Ответ сервера — карточка после решения: итог, если действие
 * успело за 20 с, или `executing`. Одобрение продолжает прогон, и его поток несёт итог и эпилог Leo. Карточка, уже
 * решённая в другом месте (409 `action_not_pending`), перечитывается и показывает, чем кончилась.
 */

type Words = { failed: string };

/** Карточку решили в другом месте — на другом экране или голосом: её итог виден здесь, а «Нужны вы» перечитывается. */
export async function rereadCard(id: string) {
  try {
    receiveCard(await proposalsApi.card(id));
  } catch (error) {
    // «Нужны вы» всё равно перечитается и уберёт карточку, если она уже не ждёт.
    console.warn("Leo: решённую карточку не удалось перечитать", error);
  }
  proposalArrived();
}

async function decide(proposal: LeoProposal, request: () => Promise<DecidedProposal>, words: Words) {
  markBusy(proposal.id, true);
  try {
    const { run_id: runId, ...decided } = await request();
    receiveCard(decided);
    // Карточку могли собрать из пунктов дайджеста: он перечитается и покажет задачи или свободные пункты.
    digestProposalDecided(decided.id);
    return runId;
  } catch (error) {
    toast.error(words.failed, { description: apiErrorDescription(error) });
    if (error instanceof ApiError && error.code === "action_not_pending") await rereadCard(proposal.id);
    return null;
  } finally {
    markBusy(proposal.id, false);
  }
}

/** «Одобрить»: для правки текста — только выбранные замены. Поток прогона ведёт эпилог. */
export async function approveProposal(proposal: LeoProposal, acceptedChanges: number[] | undefined, words: Words) {
  const runId = await decide(proposal, () => proposalsApi.approve(proposal, acceptedChanges), words);
  if (runId !== null) void followRun(runId, proposal.id);
}

/** «Отклонить»: прогон закрывается без эпилога, его заметку покажет история. */
export const rejectProposal = (proposal: LeoProposal, words: Words) =>
  decide(proposal, () => proposalsApi.reject(proposal), words);
