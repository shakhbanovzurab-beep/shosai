import { users } from "../data/users";
import { Users } from "./users";

/** Server entry: hands the demo users to the interactive client screen. */
export function UsersScreen() {
  return <Users users={users} />;
}
