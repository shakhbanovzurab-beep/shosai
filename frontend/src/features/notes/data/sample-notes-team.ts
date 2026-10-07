import type { MeetingNote } from "../domain/types";
import { meeting, said, todo, topic } from "./demo-meetings";

// Sample data: customer, engineering and team meetings.
export const teamNotes: MeetingNote[] = [
  meeting("customer-interview-northwind", "Customer interview — Northwind", {
    folderId: "progress",
    startedAt: "2026-09-30T16:00:00Z",
    durationMinutes: 52,
    participants: [
      { name: "Priya Nair", role: "Data analyst", email: "priya@lumen.so" },
      { name: "Liam Turner", role: "Northwind, Head of Ops", email: "liam@northwind.com" },
    ],
    tags: ["Research", "Customer"],
    summary:
      "Northwind runs about 30 internal meetings a week and loses decisions between tools. They want searchable transcripts and a weekly digest of action items, and would pay for automatic follow-up emails.",
    keyPoints: [
      "Decisions get lost between chat, email and docs.",
      "A weekly action-item digest is the most requested feature.",
      "Automatic follow-up emails are a clear willingness-to-pay signal.",
    ],
    decisions: ["Add Northwind to the Leo beta list."],
    actionItems: [
      todo("c1", "Send Northwind the beta invite", "Priya Nair"),
      todo("c2", "Share interview highlights with the team", "Priya Nair", true),
    ],
    transcript: [
      said("Priya Nair", 0, "Could you walk me through what happens after one of your meetings?"),
      said(
        "Liam Turner",
        22,
        "Honestly, someone writes notes, they end up in a doc nobody opens, and decisions get lost.",
      ),
      said("Priya Nair", 74, "If you had one thing to fix that, what would it be?"),
      said(
        "Liam Turner",
        88,
        "A weekly digest of who owes what. And if it could send the follow-up emails itself, I'd pay for that today.",
      ),
    ],
    mindMap: topic(
      "Northwind",
      topic("Pain points", topic("Lost decisions"), topic("Scattered notes")),
      topic("Wishes", topic("Weekly digest"), topic("Auto follow-ups")),
      topic("Next steps", topic("Beta invite")),
    ),
  }),
  meeting("weekly-engineering-sync", "Weekly engineering sync", {
    folderId: "work",
    startedAt: "2026-09-24T10:00:00Z",
    durationMinutes: 27,
    participants: [
      { name: "Maya Chen", role: "Engineering manager", email: "maya@lumen.so" },
      { name: "Sofia Rossi", role: "Frontend engineer", email: "sofia@lumen.so" },
      { name: "Noah Kim", role: "Backend engineer", email: "noah@lumen.so" },
    ],
    tags: ["Engineering"],
    summary:
      "The streaming protocol for Leo is done and tested. File uploads are next. Noah flagged that the deploy process needs a single owner after two conflicting restarts this week.",
    keyPoints: [
      "Leo's step-by-step event stream is complete.",
      "File uploads are capped at 5 files of 10 MB each.",
      "Deploys must go through the systemd service only.",
    ],
    decisions: ["Only restart the app with systemctl."],
    actionItems: [todo("d1", "Document the deploy process", "Noah Kim")],
    transcript: [
      said("Maya Chen", 0, "Quick round. Noah, how's the streaming protocol?"),
      said("Noah Kim", 12, "Done and tested. Every agent step now arrives as its own event."),
      said("Sofia Rossi", 40, "Great, I'll start on file uploads. Five files, ten megabytes each."),
      said(
        "Noah Kim",
        71,
        "One more thing: we had two people restarting the server by hand. Let's agree deploys only go through systemd.",
      ),
    ],
    mindMap: topic(
      "Eng sync",
      topic("Leo streaming", topic("Done")),
      topic("File uploads", topic("5 × 10 MB")),
      topic("Deploys", topic("systemd only")),
    ),
  }),
  meeting("one-on-one-maya", "1:1 with Maya", {
    startedAt: "2026-10-04T15:00:00Z",
    durationMinutes: 24,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Maya Chen", role: "Engineering manager", email: "maya@lumen.so" },
    ],
    tags: ["1:1"],
    summary:
      "Maya wants to grow into a group manager role next year. We agreed she will lead the Leo beta launch end to end as a stretch project.",
    keyPoints: ["Career goal: group manager in 2027.", "Leo beta launch is the stretch project."],
    decisions: ["Maya owns the Leo beta launch."],
    actionItems: [todo("e1", "Write the launch plan outline", "Maya Chen")],
    transcript: [
      said("Arham Khan", 0, "How are you feeling about the last quarter?"),
      said("Maya Chen", 18, "Good. I'd like to take on something bigger, maybe lead a launch myself."),
      said("Arham Khan", 47, "Then the Leo beta is yours, end to end."),
    ],
    mindMap: topic(
      "1:1 Maya",
      topic("Growth", topic("Group manager")),
      topic("Stretch project", topic("Leo beta launch")),
    ),
  }),
  meeting("pricing-workshop", "Pricing workshop", {
    folderId: "goal",
    startedAt: "2026-10-01T11:00:00Z",
    durationMinutes: 64,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Priya Nair", role: "Data analyst", email: "priya@lumen.so" },
      { name: "Elena Petrova", role: "Head of Sales", email: "elena@lumen.so" },
      { name: "Noah Kim", role: "Backend engineer", email: "noah@lumen.so" },
      { name: "Diego Alvarez", role: "Designer", email: "diego@lumen.so" },
    ],
    tags: ["Pricing", "Strategy"],
    summary:
      "Explored seat-based versus usage-based pricing for Leo. Sales prefers seats for predictability; data shows heavy users would churn on usage pricing. We will test a seat plan with an agent-minutes add-on.",
    keyPoints: [
      "Seats are easier to sell and forecast.",
      "Usage pricing risks churn among the most active users.",
      "An add-on for agent minutes covers heavy usage.",
    ],
    decisions: ["Test seat pricing with an agent-minutes add-on."],
    actionItems: [
      todo("f1", "Model revenue for three seat tiers", "Priya Nair"),
      todo("f2", "Draft the pricing page", "Diego Alvarez"),
    ],
    transcript: [
      said("Elena Petrova", 0, "Customers ask for predictable bills. Seats win every sales call."),
      said("Priya Nair", 35, "Our heaviest users would pay four times more on usage pricing."),
      said("Arham Khan", 80, "So seats as the base, and an add-on for agent minutes above a threshold."),
    ],
    mindMap: topic(
      "Pricing",
      topic("Seats", topic("Predictable"), topic("Sales prefers")),
      topic("Usage", topic("Churn risk")),
      topic("Plan", topic("Seats + add-on")),
    ),
  }),
  meeting("standup-sep-29", "Daily standup", {
    folderId: "progress",
    startedAt: "2026-09-29T08:30:00Z",
    durationMinutes: 11,
    participants: [
      { name: "Maya Chen", role: "Engineering manager", email: "maya@lumen.so" },
      { name: "Sofia Rossi", role: "Frontend engineer", email: "sofia@lumen.so" },
      { name: "Noah Kim", role: "Backend engineer", email: "noah@lumen.so" },
    ],
    tags: ["Standup"],
    summary: "No blockers. Sofia finished the agent steps UI; Noah is wiring file uploads into the stream.",
    keyPoints: ["Agent steps UI is done.", "File uploads are in progress."],
    decisions: [],
    actionItems: [],
    transcript: [
      said("Sofia Rossi", 0, "Agent steps UI is merged."),
      said("Noah Kim", 9, "Working on uploads in the stream, no blockers."),
    ],
    mindMap: topic("Standup", topic("Done", topic("Steps UI")), topic("Doing", topic("Uploads"))),
  }),
];
