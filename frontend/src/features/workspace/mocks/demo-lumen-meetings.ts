import { action, said } from "./demo-rows";
import type { MeetingSeed } from "./types";

/* Meetings other Lumen members recorded and shared; they aren't in the demo user's Notes. */

const team = (team_id: string) => ({ level: "team" as const, team_id });

export const lumenMeetings: MeetingSeed[] = [
  {
    id: "onboarding-flow-review",
    // i18n-ignore: demo data, a meeting title its organizer wrote
    title: "Onboarding flow review",
    started_at: "2026-10-05T15:30:00Z",
    duration_minutes: 35,
    owner: "Diego Alvarez",
    project_id: "onboarding",
    participants: ["Diego Alvarez", "Sofia Rossi", "Priya Nair"],
    visibility: team("product"),
    transcript_shared: true,
    summary:
      "Diego walked through the new three-step onboarding. Priya's funnel data shows most drop-off at the calendar connection step, so it becomes optional and moves after the first meeting.",
    key_points: [
      "Calendar connection loses 38% of new users.",
      "A sample meeting makes the value clear before any setup.",
    ],
    decisions: ["Make calendar connection optional during onboarding."],
    actions: [
      action("Sign off the new onboarding flow", "Arham Khan", "todo", 1),
      action("Build the sample meeting step", "Sofia Rossi", "todo", 6),
    ],
    transcript: [
      said("Diego Alvarez", 0, "Three steps now: name, a sample meeting, then optional calendar."),
      said("Priya Nair", 31, "That matches the data. Calendar is where we lose people."),
      said("Sofia Rossi", 58, "I can have the sample meeting step ready next week."),
    ],
  },
  {
    id: "incident-review-stream-timeouts",
    // i18n-ignore: demo data, a meeting title its organizer wrote
    title: "Incident review: stream timeouts",
    started_at: "2026-10-03T10:00:00Z",
    duration_minutes: 30,
    owner: "Noah Kim",
    project_id: "reliability",
    participants: ["Noah Kim", "Maya Chen", "Sofia Rossi"],
    visibility: { level: "workspace", team_id: null },
    transcript_shared: true,
    summary:
      "Leo's answer stream timed out for 14 minutes on Friday after a proxy update dropped keep-alive pings. A heartbeat event every 15 seconds fixes it; alerts will page on stream errors above 2%.",
    key_points: ["The proxy closed idle connections after 60 seconds.", "No data was lost; users had to retry."],
    decisions: ["Send a heartbeat event every 15 seconds on every stream."],
    actions: [
      action("Add the stream error alert", "Noah Kim", "done", -1),
      action("Write the public incident summary", "Maya Chen", "todo", -1),
    ],
    transcript: [
      said("Noah Kim", 0, "Short version: the proxy update dropped our keep-alives."),
      said("Maya Chen", 24, "Let's send a heartbeat so we never depend on the proxy again."),
    ],
  },
  {
    id: "sales-pipeline-review",
    // i18n-ignore: demo data, a meeting title its organizer wrote
    title: "Sales pipeline review",
    started_at: "2026-10-02T13:00:00Z",
    duration_minutes: 40,
    owner: "Elena Petrova",
    project_id: "pricing",
    participants: ["Elena Petrova", "Priya Nair", "Tom Becker", "Arham Khan"],
    visibility: team("sales"),
    transcript_shared: false,
    summary:
      "Twelve Team-plan trials are active; four ask for SSO. Elena wants a clear pricing page before the next outbound push, and a customer advisory board to test the Enterprise tier.",
    key_points: ["SSO is the top blocker for larger teams.", "Trials convert best with two or more active members."],
    decisions: ["Start a customer advisory board with five Team customers."],
    actions: [
      action("Review the Team plan pricing page copy", "Arham Khan", "todo", -2),
      action("Pick a date for the customer advisory board", null, "todo", null),
      action("List the trials that asked for SSO", "Tom Becker", "todo", 3),
    ],
    transcript: [
      said("Elena Petrova", 0, "Twelve trials running. Four of them keep asking about SSO."),
      said("Arham Khan", 40, "Send me the pricing page draft, I'll review it this week."),
    ],
  },
  {
    id: "hiring-plan-q4",
    // i18n-ignore: demo data, a meeting title its organizer wrote
    title: "Hiring plan for Q4",
    started_at: "2026-09-28T16:00:00Z",
    duration_minutes: 45,
    owner: "Maya Chen",
    project_id: "hiring",
    participants: ["Maya Chen", "Arham Khan", "Elena Petrova"],
    visibility: team("leadership"),
    transcript_shared: true,
    summary:
      "Two engineering hires and one account executive for Q4. The senior frontend role is first; the interview loop gets a paid take-home instead of live coding.",
    key_points: ["Budget covers three hires this quarter.", "Interviews run in Shosai rooms so notes are shared."],
    decisions: ["Open the senior frontend role first.", "Replace live coding with a paid take-home task."],
    actions: [
      action("Write the senior frontend job post", "Arham Khan", "todo", 4),
      action("Set up the take-home task", "Maya Chen", "done", -3),
    ],
    transcript: [
      said("Maya Chen", 0, "Three hires fit the budget. I'd start with senior frontend."),
      said("Elena Petrova", 35, "And one AE for me once the pricing page is live."),
    ],
  },
  {
    id: "pricing-kickoff",
    // i18n-ignore: demo data, a meeting title its organizer wrote
    title: "Team plan pricing kickoff",
    started_at: "2026-09-17T14:00:00Z",
    duration_minutes: 50,
    owner: "Elena Petrova",
    project_id: "pricing",
    participants: ["Elena Petrova", "Arham Khan", "Priya Nair"],
    visibility: { level: "workspace", team_id: null },
    transcript_shared: true,
    summary:
      "First pass at Team pricing. The group leaned towards billing only active users each month; Priya will check how that compares with seat pricing in the workshop.",
    key_points: ["Customers dislike paying for idle seats.", "Finance needs a predictable monthly number."],
    decisions: ["Bill the Team plan per active user each month."],
    actions: [action("Draft the Team plan one-pager", "Arham Khan", "done", -12)],
    transcript: [
      said("Elena Petrova", 0, "What if we only bill people who actually used Leo that month?"),
      said("Priya Nair", 28, "Worth modelling against seats before we commit."),
    ],
  },
];

/** A decision that a later meeting replaced: the kickoff's pricing idea gave way to the workshop's. */
export const SUPERSEDED: Record<string, string> = { "pricing-kickoff--d0": "pricing-workshop--d0" };
