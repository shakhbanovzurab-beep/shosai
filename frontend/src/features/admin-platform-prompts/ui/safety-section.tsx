import { ConfirmActionsCard } from "./safety-confirm-card";
import { RulesCard } from "./safety-rules-card";
import { BlockedTopicsCard } from "./safety-topics-card";

/** Guardrails: ordered rules, topics Leo declines, and agent actions that need the user's go-ahead. */
export function SafetySection() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <RulesCard />
      <BlockedTopicsCard />
      <ConfirmActionsCard />
    </div>
  );
}
