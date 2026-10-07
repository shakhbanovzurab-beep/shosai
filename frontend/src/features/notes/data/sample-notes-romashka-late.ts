import type { MeetingNote } from "../domain/types";
import { meeting, said, todo, topic } from "./demo-meetings";

// Sample data: Romashka client meetings from late September onwards.
export const romashkaLateNotes: MeetingNote[] = [
  meeting("romashka-rollout-sync", "Rollout sync", {
    startedAt: "2026-09-24T10:00:00Z",
    durationMinutes: 45,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Ivan Petrov", role: "Solutions engineer", email: "ivan@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
      { name: "Dmitry Volkov", role: "Romashka, IT lead", email: "d.volkov@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "Planned the order of the Romashka rollout after the pilot. Olga asked whether each department needs its own bot. The team reversed the kickoff decision and added Telegram to the first release.",
    keyPoints: [
      "Departments roll out one at a time after the pilot.",
      "Open question: one bot or a bot per department.",
      "Telegram moves into the first release.",
    ],
    decisions: ["Telegram goes into the first release."],
    actionItems: [
      todo("rl1", "Add Telegram to the first release plan", "Ivan Petrov"),
      todo("rl2", "Decide on one bot or a bot per department", "Arham Khan"),
    ],
    transcript: [
      said("Arham Khan", 0, "Today is about the rollout order after the pilot."),
      said("Olga Smirnova", 300, "Sales first, then Support, then the back office."),
      said("Olga Smirnova", 1210, "Do we need a separate bot for each department?"),
      said("Dmitry Volkov", 1260, "One bot would be easier for us to maintain."),
      said("Arham Khan", 1300, "Let’s check the permissions model before we decide."),
      said("Olga Smirnova", 1880, "Our staff keep asking for notifications in Telegram."),
      said("Ivan Petrov", 1934, "Let’s add Telegram to the first release."),
      said("Olga Smirnova", 1975, "Agreed. It’s where people actually read messages."),
      said("Arham Khan", 2600, "Good. I’ll update the release plan."),
    ],
    mindMap: topic(
      "Rollout",
      topic("Order", topic("Sales → Support"), topic("Back office")),
      topic("Bots", topic("One or per department")),
      topic("Telegram", topic("First release")),
    ),
  }),
  meeting("romashka-sync-0926", "Romashka weekly sync", {
    startedAt: "2026-09-26T10:00:00Z",
    durationMinutes: 25,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Ivan Petrov", role: "Solutions engineer", email: "ivan@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
      { name: "Dmitry Volkov", role: "Romashka, IT lead", email: "d.volkov@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "Short sync. Olga asked to move the contract to next week. Dmitry reported that the test server keeps dropping connections, which slows down pilot testing.",
    keyPoints: ["The contract moves to next week.", "The test server is unstable."],
    decisions: ["The contract moves to next week."],
    actionItems: [
      todo("rl3", "Put the contract on next week’s agenda", "Arham Khan"),
      todo("rl4", "Investigate the test server connection drops", "Ivan Petrov"),
    ],
    transcript: [
      said("Arham Khan", 0, "Let’s keep this one short."),
      said("Arham Khan", 330, "Olga, are we ready to sign this week?"),
      said("Olga Smirnova", 365, "Let’s move the contract to next week."),
      said("Arham Khan", 400, "No problem, I’ll put it on next week’s agenda."),
      said("Ivan Petrov", 860, "Dmitry, how is pilot testing going?"),
      said("Dmitry Volkov", 900, "The test server keeps dropping connections."),
      said("Ivan Petrov", 950, "I’ll get our infrastructure team on it today."),
      said("Arham Khan", 1400, "Thanks, all. Talk next week."),
    ],
    mindMap: topic(
      "Weekly sync",
      topic("Contract", topic("Next week")),
      topic("Test server", topic("Dropping connections")),
    ),
  }),
  meeting("romashka-licensing-call", "Romashka: licensing call", {
    startedAt: "2026-09-27T10:00:00Z",
    durationMinutes: 20,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Dmitry Volkov", role: "Romashka, IT lead", email: "d.volkov@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "Arham and Dmitry went through the licensing options. To settle the open price per seat, Romashka is switching to the Team plan.",
    keyPoints: ["The price per seat was the open question.", "The Team plan fits Romashka’s headcount."],
    decisions: ["Romashka moves to the Team plan."],
    actionItems: [todo("rl5", "Send Romashka the Team plan quote", "Arham Khan")],
    transcript: [
      said("Arham Khan", 0, "Thanks for jumping on, Dmitry. Let’s settle licensing."),
      said("Dmitry Volkov", 120, "The price per seat is still what’s holding us up."),
      said("Arham Khan", 410, "The Team plan has a flat price up to five hundred users."),
      said("Dmitry Volkov", 780, "That fits our headcount and makes budgeting easier."),
      said("Dmitry Volkov", 860, "We’re switching to the Team plan."),
      said("Arham Khan", 900, "Great, I’ll send you the quote today."),
    ],
    mindMap: topic(
      "Licensing",
      topic("Seat price", topic("Open question")),
      topic("Team plan", topic("Flat price"), topic("Chosen")),
    ),
  }),
  meeting("romashka-sync-1003", "Romashka weekly sync", {
    startedAt: "2026-10-03T10:00:00Z",
    durationMinutes: 30,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Ivan Petrov", role: "Solutions engineer", email: "ivan@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
      { name: "Dmitry Volkov", role: "Romashka, IT lead", email: "d.volkov@romashka.ru" },
    ],
    tags: ["Romashka", "Client"],
    summary:
      "Romashka sent over the final list of pilot users. The remaining blocker is SSO: Ivan committed to getting Romashka SSO access by Monday so the admins can start testing.",
    keyPoints: ["The final pilot user list is in.", "SSO access is the last step before admin testing."],
    decisions: ["Pilot users are imported from the final list."],
    actionItems: [
      todo("rl6", "Get Romashka SSO access by Monday", "Ivan Petrov"),
      todo("rl7", "Import the pilot users", "Ivan Petrov"),
    ],
    transcript: [
      said("Arham Khan", 0, "Morning. Let’s start with the pilot."),
      said("Olga Smirnova", 190, "We sent over the final list of pilot users."),
      said("Ivan Petrov", 230, "Got it, thanks. I’ll import them this afternoon."),
      said("Dmitry Volkov", 460, "Our admins still can’t sign in. When will SSO be ready?"),
      said("Ivan Petrov", 510, "I’ll get you SSO access by Monday."),
      said("Dmitry Volkov", 560, "Good. Then the admins can start testing on Tuesday."),
      said("Arham Khan", 1650, "That’s everything for today. Thanks, all."),
    ],
    mindMap: topic("Weekly sync", topic("Pilot", topic("Final user list")), topic("SSO", topic("Access by Monday"))),
  }),
  meeting("meeting-oct-05-1718", "Meeting Oct 5, 17:18", {
    startedAt: "2026-10-05T17:18:00Z",
    durationMinutes: 22,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Olga Smirnova", role: "Romashka, project lead", email: "o.smirnova@romashka.ru" },
    ],
    tags: ["Romashka"],
    summary:
      "Ad-hoc call from Olga about the Romashka rollout. Their admins are asking about SSO and want to start testing tomorrow; Arham will check the status with Ivan.",
    keyPoints: ["Romashka admins are still waiting on SSO.", "They want to start testing tomorrow."],
    decisions: [],
    actionItems: [todo("rl8", "Check SSO status with Ivan and update Olga", "Arham Khan")],
    transcript: [
      said("Arham Khan", 0, "Hi Olga, what’s up?"),
      said("Olga Smirnova", 95, "About the Romashka rollout — the admins are asking about SSO."),
      said("Arham Khan", 130, "Ivan was going to get you access today. Nothing yet?"),
      said("Olga Smirnova", 150, "Nothing so far, and they want to start testing tomorrow."),
      said("Arham Khan", 190, "I’ll check with Ivan and get back to you tonight."),
      said("Olga Smirnova", 1250, "Thanks. Talk soon."),
    ],
    mindMap: topic("Ad-hoc call", topic("SSO", topic("Admins waiting")), topic("Next step", topic("Check with Ivan"))),
  }),
];
