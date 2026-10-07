import { BehaviorModelCard } from "./behavior-model-card";
import { OverridesCard } from "./behavior-overrides-card";
import { ResponseCard } from "./behavior-response-card";

/** Platform-wide defaults for tone, language, model and what users may override. */
export function BehaviorSection() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ResponseCard />
      <BehaviorModelCard />
      <OverridesCard />
    </div>
  );
}
