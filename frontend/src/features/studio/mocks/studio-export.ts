import { getContext } from "./demo-context";
import { listModels } from "./demo-models";
import { listPrompts } from "./demo-prompts";

/** Studio's part of the demo's "download your data" file: context, prompts and each role's model settings. */
export const exportStudioData = () => ({
  context: getContext(),
  prompts: listPrompts(),
  models: listModels().roles,
});
