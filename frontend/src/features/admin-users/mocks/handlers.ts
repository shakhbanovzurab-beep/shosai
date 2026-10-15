import { type MockRoute, mockRoute } from "@/mocks/routing";

import { cardOf, findUsers, setState } from "./demo-users";

type Params = { params: Promise<{ user_id: string }> };

const refused = (code: string, status: number) =>
  Response.json({ error: { code, request_id: "mock-request" }, detail: code }, { status });

const usersRoute = {
  GET(request: Request) {
    const query = new URL(request.url).searchParams;
    const email = query.get("email");
    const name = query.get("name");
    if ((email === null) === (name === null)) return refused("search_needs_email_or_name", 422);
    return Response.json({ items: findUsers(email, name), next_cursor: null });
  },
};

const userRoute = {
  async GET(_request: Request, { params }: Params) {
    const card = cardOf((await params).user_id);
    return card ? Response.json(card) : refused("user_not_found", 404);
  },
};

function acting(from: "active" | "frozen", to: "active" | "frozen") {
  return {
    async POST(_request: Request, { params }: Params) {
      const id = (await params).user_id;
      const card = cardOf(id);
      if (!card) return refused("user_not_found", 404);
      if (card.user.state !== from && card.user.state !== to) return refused("account_state_conflict", 409);
      setState(id, to);
      return Response.json(cardOf(id));
    },
  };
}

export const handlers: MockRoute[] = [
  mockRoute("/v1/admin/users", usersRoute, ["GET"]),
  mockRoute("/v1/admin/users/:user_id", userRoute, ["GET"]),
  mockRoute("/v1/admin/users/:user_id/block", acting("active", "frozen"), ["POST"]),
  mockRoute("/v1/admin/users/:user_id/unblock", acting("frozen", "active"), ["POST"]),
];
