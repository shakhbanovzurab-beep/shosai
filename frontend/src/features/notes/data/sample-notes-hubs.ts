import type { MeetingNote } from "../domain/types";
import { meeting, said, todo, topic } from "./demo-meetings";

// Sample data: hiring, release and pilot meetings referenced by the Hub.
export const hubNotes: MeetingNote[] = [
  meeting("hiring-design-sync", "Designer hiring sync", {
    startedAt: "2026-09-29T09:00:00Z",
    durationMinutes: 30,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Maya Chen", role: "Engineering manager", email: "maya@lumen.so" },
      { name: "Sofia Rossi", role: "Product designer", email: "sofia@lumen.so" },
    ],
    tags: ["Hiring"],
    summary:
      "Reviewed the product designer pipeline. Three candidates are left, and Maya wants the portfolio review closed by Friday. We agreed on the salary range for the role.",
    keyPoints: [
      "Three candidates remain in the pipeline.",
      "The portfolio review closes by Friday.",
      "The salary range is agreed.",
    ],
    decisions: ["Close the portfolio review by Friday.", "Salary range agreed for the designer role."],
    actionItems: [
      todo("hb1", "Close the portfolio review", "Maya Chen", true),
      todo("hb2", "Share the salary range with the recruiter", "Arham Khan", true),
    ],
    transcript: [
      said("Maya Chen", 0, "Let’s go through the designer pipeline."),
      said("Sofia Rossi", 60, "Three candidates are left. Lena’s portfolio is the strongest so far."),
      said("Maya Chen", 240, "Let’s close the portfolio review by Friday."),
      said("Sofia Rossi", 275, "Works for me. I’ll finish my notes by Thursday."),
      said("Maya Chen", 560, "Last thing: compensation. Did finance come back?"),
      said("Arham Khan", 610, "We agreed on the salary range."),
      said("Maya Chen", 650, "Great, then we can move fast once we pick someone."),
    ],
    mindMap: topic(
      "Designer hiring",
      topic("Pipeline", topic("3 candidates"), topic("Portfolio review by Friday")),
      topic("Offer", topic("Salary range agreed")),
    ),
  }),
  meeting("designer-interview-debrief", "Designer interview debrief", {
    startedAt: "2026-10-02T15:00:00Z",
    durationMinutes: 25,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Maya Chen", role: "Engineering manager", email: "maya@lumen.so" },
      { name: "Sofia Rossi", role: "Product designer", email: "sofia@lumen.so" },
    ],
    tags: ["Hiring"],
    summary:
      "Debrief after the final designer interviews. Sofia recommended making Lena an offer, and the panel agreed. Arham will send the offer the same day.",
    keyPoints: ["Lena was the strongest candidate in the final round.", "The panel agreed on an offer."],
    decisions: ["Make Lena an offer."],
    actionItems: [
      todo("hb3", "Send Lena the offer", "Arham Khan"),
      todo("hb4", "Let the other candidates know", "Maya Chen"),
    ],
    transcript: [
      said("Arham Khan", 0, "So, how did the final interviews go?"),
      said("Maya Chen", 40, "Both were solid, but Lena’s case study stood out."),
      said("Sofia Rossi", 300, "I’d make Lena an offer."),
      said("Maya Chen", 340, "Agreed. Her systems thinking is exactly what we need."),
      said("Maya Chen", 780, "Who sends the offer, and when?"),
      said("Arham Khan", 820, "I’ll send the offer today."),
      said("Maya Chen", 860, "Then I’ll let the other candidates know on Monday."),
    ],
    mindMap: topic(
      "Interview debrief",
      topic("Candidates", topic("Lena stood out")),
      topic("Offer", topic("Sent today")),
    ),
  }),
  meeting("release-2-planning", "Release 2.0 planning", {
    startedAt: "2026-09-13T09:00:00Z",
    durationMinutes: 45,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Maya Chen", role: "Engineering manager", email: "maya@lumen.so" },
      { name: "Noah Kim", role: "Backend engineer", email: "noah@lumen.so" },
    ],
    tags: ["Release"],
    summary:
      "Planned the scope of Release 2.0. Noah raised that the backlog keeps growing, and Maya asked to freeze the scope so the team can commit to a date.",
    keyPoints: ["The 2.0 backlog keeps growing.", "Scope must be frozen before committing to a date."],
    decisions: ["Freeze the 2.0 scope."],
    actionItems: [
      todo("hb5", "Freeze the 2.0 scope", "Maya Chen"),
      todo("hb6", "List the must-have items for 2.0", "Noah Kim", true),
    ],
    transcript: [
      said("Arham Khan", 0, "Goal for today: agree what goes into 2.0."),
      said("Noah Kim", 120, "The backlog has grown by twenty items since last month."),
      said("Arham Khan", 900, "Some of those are small. Can we squeeze them in?"),
      said("Noah Kim", 1440, "Every small item pushes the date again."),
      said("Maya Chen", 1500, "We need to freeze the scope for 2.0."),
      said("Arham Khan", 1560, "Fine. Noah, can you list the must-haves?"),
      said("Noah Kim", 1590, "Sure, I’ll have it by tomorrow."),
    ],
    mindMap: topic(
      "Release 2.0",
      topic("Backlog", topic("+20 items")),
      topic("Scope", topic("Freeze"), topic("Must-haves")),
    ),
  }),
  meeting("pilot-alpha-wrapup", "Pilot Alpha wrap-up", {
    startedAt: "2026-06-20T12:00:00Z",
    durationMinutes: 30,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Maya Chen", role: "Engineering manager", email: "maya@lumen.so" },
    ],
    tags: ["Pilot"],
    summary:
      "Wrapped up Pilot Alpha. Usage held up through the final week and the last open bugs were fixed. The next step is a written summary of the results.",
    keyPoints: ["Usage held up through the final week.", "No open bugs remain.", "The results need a write-up."],
    decisions: ["Pilot Alpha is closed."],
    actionItems: [todo("hb7", "Write up the pilot results", "Arham Khan")],
    transcript: [
      said("Maya Chen", 0, "Final numbers are in. Usage held up through the last week."),
      said("Arham Khan", 95, "Good. Any open issues left?"),
      said("Maya Chen", 130, "Two small bugs, both fixed on Thursday."),
      said("Arham Khan", 420, "The pilot is done; let’s write up the results."),
      said("Maya Chen", 460, "I can pull the usage charts for it."),
      said("Arham Khan", 1700, "Thanks. Let’s share it with the team next week."),
    ],
    mindMap: topic(
      "Pilot Alpha",
      topic("Results", topic("Usage held up"), topic("Bugs fixed")),
      topic("Next step", topic("Write-up")),
    ),
  }),
];
