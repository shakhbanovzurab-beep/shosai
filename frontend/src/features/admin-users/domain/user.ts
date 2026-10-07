export type UserStatus = "Active" | "Pending invite" | "Deactivated" | "Locked" | "Suspended";

const teamValues = [
  "Platform",
  "Growth",
  "Revenue",
  "Customer Ops",
  "Internal Tools",
  "Compliance",
  "People Ops",
  "Finance",
] as const;

export type UserTeam = (typeof teamValues)[number];

export type UserRow = {
  email: string;
  joinedDate: string;
  lastActive: number;
  name: string;
  role: string;
  status: UserStatus;
  team: UserTeam;
  workspace: string[];
};

export const filters = {
  role: [
    "All",
    "Workspace Owner",
    "Admin",
    "Billing Admin",
    "Security Admin",
    "Team Lead",
    "Contributor",
    "Guest",
    "Read-only",
  ],
  team: ["All", ...teamValues],
  status: ["All", "Active", "Pending invite", "Deactivated", "Locked", "Suspended"],
  workspace: ["All", "Weblabs Studio", "Sandbox", "Internal Tools", "Acme Inc."],
};
