/*
 * The demo's active projects. Titles are what the user wrote, so they stay as written in every interface
 * language; the status is a code the interface words.
 */

export type ProjectStatus = "inProgress" | "planning";

export type Project = {
  id: string;
  title: string;
  status: ProjectStatus;
  /** 0–100. */
  progress: number;
  /** The due day, counted in calendar days from today. */
  dueInDays: number;
};

const project = (id: string, title: string, status: ProjectStatus, progress: number, dueInDays: number): Project => ({
  id,
  title,
  status,
  progress,
  dueInDays,
});

export const projects: Project[] = [
  project("q2-roadmap", "Q2 Roadmap", "inProgress", 68, 9),
  project("website-redesign", "Website Redesign", "planning", 42, 21),
  project("onboarding", "Onboarding", "planning", 31, 18),
];
