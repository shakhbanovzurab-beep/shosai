export type Role = {
  role: string;
  group: string;
  accessLevel: string;
  users: number;
  permissionSets: string[];
  lastReview: string;
  owner: string;
  status: "Active" | "Needs review";
};

export function getRoleTypeFilter(groupFilter: string) {
  if (groupFilter === "System roles") {
    return "System";
  }

  if (groupFilter === "Custom roles") {
    return "Custom";
  }

  return "All";
}

export function getRoleGroupFilterValue(typeFilter: string) {
  if (typeFilter === "System") {
    return "System roles";
  }

  if (typeFilter === "Custom") {
    return "Custom roles";
  }

  return undefined;
}
