import { workspaceRoute } from "@/features/admin-workspaces/server";

export const dynamic = "force-dynamic";
export const { GET, PATCH, DELETE } = workspaceRoute;
