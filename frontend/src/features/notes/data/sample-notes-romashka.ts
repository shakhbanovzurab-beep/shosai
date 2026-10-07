import type { MeetingNote } from "../domain/types";
import { meeting, said, todo, topic } from "./demo-meetings";

// Sample data: Romashka client meetings, from the intro call to the mid-September syncs.
export const romashkaNotes: MeetingNote[] = [
  meeting("romashka-intro-call", "Romashka intro call", {
    startedAt: "2026-06-10T10:00:00Z",
    durationMinutes: 35,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Ivan Petrov", role: "Solutions engineer", email: "ivan@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "First call with Romashka. Olga walked us through their teams and what they expect from a rollout. We offered a training session for their admins as part of onboarding.",
    keyPoints: ["Romashka’s admins will own the rollout.", "Onboarding includes a training session for admins."],
    decisions: ["Prepare a rollout proposal for Romashka."],
    actionItems: [
      todo("rk1", "Run a training session for Romashka admins", "Arham Khan"),
      todo("rk2", "Send Romashka the product overview", "Ivan Petrov", true),
    ],
    transcript: [
      said("Arham Khan", 0, "Thanks for making time, Olga. Ivan is joining from our side."),
      said("Olga Smirnova", 45, "Happy to. We’re about four hundred people in five departments."),
      said("Ivan Petrov", 380, "Who would run the rollout on your side?"),
      said("Olga Smirnova", 410, "Our admins. They’ll manage users and access themselves."),
      said("Arham Khan", 1290, "We’ll run a training session for your admins."),
      said("Olga Smirnova", 1320, "That would help a lot. They’re new to tools like this."),
      said("Ivan Petrov", 1980, "I’ll send over the product overview after the call."),
    ],
    mindMap: topic(
      "Romashka intro",
      topic("Company", topic("~400 people"), topic("5 departments")),
      topic("Rollout", topic("Admins own it"), topic("Admin training")),
      topic("Next steps", topic("Product overview")),
    ),
  }),
  meeting("romashka-kickoff", "Romashka kickoff", {
    startedAt: "2026-07-18T10:00:00Z",
    durationMinutes: 50,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Ivan Petrov", role: "Solutions engineer", email: "ivan@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
      { name: "Dmitry Volkov", role: "Romashka, IT lead", email: "d.volkov@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "Kickoff for the Romashka rollout, with their IT lead joining. We walked through the pilot, SSO requirements and which channels are in scope. Olga ruled out a Telegram integration.",
    keyPoints: ["Pilot first, in Sales and Support.", "Dmitry needs SSO.", "Telegram is out of scope."],
    decisions: ["No Telegram integration.", "Pilot with two departments first."],
    actionItems: [
      todo("rk3", "Share the rollout timeline with Romashka", "Arham Khan", true),
      todo("rk4", "Send the SSO requirements", "Dmitry Volkov", true),
    ],
    transcript: [
      said("Arham Khan", 0, "Welcome, everyone. Dmitry, glad you could join us."),
      said("Dmitry Volkov", 30, "Thanks. I’m mostly here for the SSO and security questions."),
      said("Ivan Petrov", 420, "We suggest a pilot with two departments before a full rollout."),
      said("Olga Smirnova", 455, "Two works. Sales and Support are the obvious ones."),
      said("Ivan Petrov", 1080, "Some clients ask for Telegram notifications. Is that relevant?"),
      said("Olga Smirnova", 1120, "Let’s be clear: we’re definitely not doing Telegram."),
      said("Dmitry Volkov", 1500, "For SSO, I’ll send you our requirements this week."),
      said("Arham Khan", 2880, "Great. I’ll share the full timeline by Monday."),
    ],
    mindMap: topic(
      "Kickoff",
      topic("Pilot", topic("Sales"), topic("Support")),
      topic("SSO", topic("Requirements")),
      topic("Channels", topic("No Telegram")),
    ),
  }),
  meeting("romashka-interface-review", "Romashka: interface review", {
    startedAt: "2026-08-01T11:00:00Z",
    durationMinutes: 40,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Ivan Petrov", role: "Solutions engineer", email: "ivan@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "Reviewed the first interface draft with Olga. She liked the meeting library but wants a simpler admin screen. Ivan will rework the mockup and leave Telegram out, as agreed at the kickoff.",
    keyPoints: ["The meeting library works.", "The admin screen is too busy.", "No Telegram in the mockup."],
    decisions: ["Simplify the admin screen."],
    actionItems: [
      todo("rk5", "Prepare the interface mockup without Telegram", "Ivan Petrov"),
      todo("rk6", "List the admin settings Romashka needs", "Olga Smirnova", true),
    ],
    transcript: [
      said("Ivan Petrov", 0, "I’ll share my screen. This is the first draft of the interface."),
      said("Olga Smirnova", 210, "The meeting library is clear. People will find this easy."),
      said("Olga Smirnova", 640, "The admin screen is too busy, though."),
      said("Arham Khan", 700, "Fair. Which settings do your admins need on day one?"),
      said("Olga Smirnova", 735, "Users, groups and access. I’ll send you the full list."),
      said("Arham Khan", 1400, "And the channels stay as agreed at the kickoff?"),
      said("Ivan Petrov", 1445, "I’ll prepare the interface mockup without Telegram."),
    ],
    mindMap: topic(
      "Interface review",
      topic("Library", topic("Clear")),
      topic("Admin screen", topic("Too busy"), topic("Users, groups, access")),
      topic("Mockup", topic("No Telegram")),
    ),
  }),
  meeting("romashka-sync-0912", "Romashka weekly sync", {
    startedAt: "2026-09-12T10:00:00Z",
    durationMinutes: 30,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Ivan Petrov", role: "Solutions engineer", email: "ivan@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
      { name: "Dmitry Volkov", role: "Romashka, IT lead", email: "d.volkov@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "Weekly check-in on the Romashka rollout. The supply contract is still with Romashka’s lawyers. Dmitry flagged SSO as the main launch risk: without it, admins can’t log in on launch day.",
    keyPoints: ["The supply contract is with Romashka’s lawyers.", "SSO is the main launch risk."],
    decisions: ["Treat SSO as a launch blocker."],
    actionItems: [
      todo("rk7", "Follow up with legal on the supply contract", "Olga Smirnova"),
      todo("rk8", "Finish the SSO setup before launch", "Ivan Petrov"),
    ],
    transcript: [
      said("Arham Khan", 0, "Morning, everyone. Let’s start with a quick status round."),
      said("Ivan Petrov", 40, "Pilot workspaces are set up for both departments."),
      said("Arham Khan", 702, "Where are we with the supply contract?"),
      said("Olga Smirnova", 750, "We’re waiting for our lawyers."),
      said("Arham Khan", 820, "Okay, let’s check again next week."),
      said("Ivan Petrov", 1050, "SSO is still in testing on our side."),
      said("Dmitry Volkov", 1100, "If SSO slips, the admins won’t be able to log in on launch day."),
      said("Ivan Petrov", 1150, "Then we treat it as a blocker and prioritize it."),
    ],
    mindMap: topic(
      "Weekly sync",
      topic("Contract", topic("Waiting on lawyers")),
      topic("SSO", topic("Launch risk")),
      topic("Pilot", topic("Workspaces ready")),
    ),
  }),
  meeting("romashka-sync-0919", "Romashka weekly sync", {
    startedAt: "2026-09-19T10:00:00Z",
    durationMinutes: 30,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Ivan Petrov", role: "Solutions engineer", email: "ivan@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
      { name: "Dmitry Volkov", role: "Romashka, IT lead", email: "d.volkov@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "The price per seat is still open, so licensing can’t be finalized. Olga will send the list of pilot users, and Ivan’s team will put together a report on the pilot.",
    keyPoints: ["The price per seat isn’t agreed.", "Romashka sends the pilot users.", "A pilot report is planned."],
    decisions: ["Ivan’s team owns the pilot report."],
    actionItems: [
      todo("rk9", "Propose a price per seat to Romashka", "Arham Khan"),
      todo("rk10", "Send the list of pilot users", "Olga Smirnova", true),
      todo("rk11", "Put together a report on the pilot", "Ivan Petrov"),
    ],
    transcript: [
      said("Arham Khan", 0, "Let’s pick up where we left off last week."),
      said("Arham Khan", 520, "Dmitry, is anything still blocking licensing?"),
      said("Dmitry Volkov", 552, "The price per seat isn’t agreed yet."),
      said("Arham Khan", 600, "Okay, I’ll come back to you with a proposal."),
      said("Ivan Petrov", 940, "For the pilot, we still need to know who’s taking part."),
      said("Olga Smirnova", 980, "We’ll send you the list of pilot users."),
      said("Olga Smirnova", 1260, "How will we know if the pilot worked?"),
      said("Ivan Petrov", 1300, "We’ll put together a report on the pilot."),
    ],
    mindMap: topic(
      "Weekly sync",
      topic("Licensing", topic("Seat price open")),
      topic("Pilot", topic("User list"), topic("Pilot report")),
    ),
  }),
];
