import { roles } from "../data/roles";
import { Roles } from "./roles";

/** Server entry: hands the demo roles to the interactive client screen. */
export function RolesScreen() {
  return <Roles roles={roles} />;
}
