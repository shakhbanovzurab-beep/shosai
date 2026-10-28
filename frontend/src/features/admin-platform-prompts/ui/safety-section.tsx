import { RulesCard } from "./safety-rules-card";
import { BlockedTopicsCard } from "./safety-topics-card";

/** Ограничения слоя платформы: правила по порядку и темы, которые Leo не обсуждает. */
export function SafetySection() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <RulesCard />
      <BlockedTopicsCard />
    </div>
  );
}
