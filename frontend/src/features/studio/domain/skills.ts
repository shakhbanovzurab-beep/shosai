/** skills.sh ids are "owner/repo/name"; installed skills keep the full folder path. Same repo and name is a match. */
export const sameSkill = (candidate: string, installed: string) => {
  if (candidate === installed) return true;
  const c = candidate.split("/");
  const i = installed.split("/");
  return c[0] === i[0] && c[1] === i[1] && c.at(-1) === i.at(-1);
};
