import { getContext } from "./demo-context";
import { listModels } from "./demo-models";
import { listPrompts } from "./demo-prompts";
import { listSkills } from "./demo-skills";

/** Studio's part of the demo's "download your data" file: context, prompts, skills and each role's model settings. */
export const exportStudioData = () => ({
  context: getContext(),
  prompts: listPrompts(),
  skills: listSkills(),
  models: listModels().roles,
});
