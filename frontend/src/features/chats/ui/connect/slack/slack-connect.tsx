"use client";

import { useState } from "react";

import type { ChatSettings } from "../../../domain/contract";
import type { SlackChannel } from "../../../domain/slack-contract";
import { StepFocus } from "../step-focus";
import { BindStep } from "./bind-step";
import { ChannelsStep } from "./channels-step";
import { WorkspaceStep } from "./workspace-step";

/*
 * Подключение Slack (§3.3 плана): пространство Slack (установить или выбрать) → каналы → привязка каждого,
 * режим и согласие. Назад с привязки — к тем же отмеченным каналам.
 */

type Phase =
  | { step: "workspace" }
  | { step: "channels"; installationId: string; picked: SlackChannel[] }
  | { step: "bind"; installationId: string; picked: SlackChannel[] };

export function SlackConnect({
  workspaceId,
  settings,
  app,
  onDone,
}: {
  workspaceId: string;
  settings: ChatSettings;
  app: string;
  onDone: () => void;
}) {
  const [phase, setPhase] = useState<Phase>({ step: "workspace" });

  if (phase.step === "workspace")
    return (
      <StepFocus key="workspace">
        <WorkspaceStep
          workspaceId={workspaceId}
          onPick={(installationId) => setPhase({ step: "channels", installationId, picked: [] })}
        />
      </StepFocus>
    );
  if (phase.step === "channels")
    return (
      <StepFocus key="channels">
        <ChannelsStep
          workspaceId={workspaceId}
          installationId={phase.installationId}
          app={app}
          initial={phase.picked}
          onBack={() => setPhase({ step: "workspace" })}
          onNext={(picked) => setPhase({ step: "bind", installationId: phase.installationId, picked })}
        />
      </StepFocus>
    );
  return (
    <StepFocus key="bind">
      <BindStep
        workspaceId={workspaceId}
        settings={settings}
        app={app}
        installationId={phase.installationId}
        picked={phase.picked}
        onBack={() => setPhase({ step: "channels", installationId: phase.installationId, picked: phase.picked })}
        onDone={onDone}
      />
    </StepFocus>
  );
}
