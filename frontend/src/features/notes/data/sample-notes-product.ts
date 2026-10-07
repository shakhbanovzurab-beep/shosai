import type { MeetingNote } from "../domain/types";
import { meeting, said, todo, topic } from "./demo-meetings";

// Sample data until meetings are recorded and transcribed for real: product and design meetings.
export const productNotes: MeetingNote[] = [
  meeting("q4-roadmap-review", "Q4 roadmap review", {
    folderId: "goal",
    startedAt: "2026-10-05T09:00:00Z",
    durationMinutes: 48,
    participants: [
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Maya Chen", role: "Engineering manager", email: "maya@lumen.so" },
      { name: "Diego Alvarez", role: "Designer", email: "diego@lumen.so" },
      { name: "Priya Nair", role: "Data analyst", email: "priya@lumen.so" },
    ],
    tags: ["Roadmap", "Planning"],
    summary:
      "The team agreed to focus Q4 on the Leo agent and the new Notes experience. Mobile parity moves to Q1 so engineering can finish the agent backend. Analytics will define success metrics for Leo before the beta.",
    keyPoints: [
      "Leo agent backend is the top engineering priority for October.",
      "Notes needs transcript search and mind maps before the beta.",
      "Mobile parity is postponed to Q1 to protect the agent timeline.",
      "Beta opens to 50 customers in mid-November.",
    ],
    decisions: ["Move mobile parity to Q1.", "Ship the Leo beta behind a feature flag on November 16."],
    actionItems: [
      todo("a1", "Draft the Leo beta success metrics", "Priya Nair"),
      todo("a2", "Break the agent backend into weekly milestones", "Maya Chen", true),
      todo("a3", "Prepare Notes mind map explorations", "Diego Alvarez"),
    ],
    transcript: [
      said(
        "Arham Khan",
        0,
        "Thanks for joining. The goal today is to lock the Q4 roadmap, and I'd like to leave with a clear top priority.",
      ),
      said(
        "Maya Chen",
        42,
        "From engineering, the agent backend is the biggest piece. If we keep mobile parity in Q4 we'll be stretched thin.",
      ),
      said(
        "Diego Alvarez",
        95,
        "Design is ready for Notes. The open question is the mind map view; I'd like a week to explore layouts.",
      ),
      said(
        "Priya Nair",
        151,
        "Before a beta we need success metrics for Leo. I'd suggest task completion rate and time saved per week.",
      ),
      said(
        "Arham Khan",
        214,
        "Then let's move mobile parity to Q1 and ship the Leo beta behind a flag in mid-November.",
      ),
      said("Maya Chen", 248, "That works. I'll split the backend into weekly milestones by Friday."),
    ],
    mindMap: topic(
      "Q4 roadmap",
      topic("Leo agent", topic("Backend milestones"), topic("Beta on Nov 16"), topic("Success metrics")),
      topic("Notes", topic("Transcript search"), topic("Mind maps")),
      topic("Mobile parity", topic("Moved to Q1")),
    ),
  }),
  meeting("leo-design-critique", "Leo chat design critique", {
    folderId: "work",
    startedAt: "2026-10-02T14:30:00Z",
    durationMinutes: 35,
    participants: [
      { name: "Diego Alvarez", role: "Designer", email: "diego@lumen.so" },
      { name: "Arham Khan", role: "Product lead", email: "arham@lumen.so" },
      { name: "Sofia Rossi", role: "Frontend engineer", email: "sofia@lumen.so" },
    ],
    tags: ["Design", "Leo"],
    summary:
      "Reviewed the Leo chat panel. The team liked the visible agent steps but wants them to fold away once the answer starts. Voice mode should be the default action in an empty composer, like ChatGPT.",
    keyPoints: [
      "Agent steps build trust, but they compete with the answer once it arrives.",
      "The composer should feel like a single row until the text wraps.",
      "Full-screen mode needs a smooth morph, not a jump.",
    ],
    decisions: ["Collapse steps automatically when the answer starts.", "Make voice mode the default composer action."],
    actionItems: [
      todo("b1", "Prototype the full-screen morph", "Sofia Rossi", true),
      todo("b2", "Write copy for the voice mode states", "Diego Alvarez"),
    ],
    transcript: [
      said("Diego Alvarez", 0, "Let's start with the steps list. I think it's the strongest part of the panel."),
      said("Arham Khan", 31, "Agreed, but once the answer streams in, the steps push it down. Can they fold away?"),
      said(
        "Sofia Rossi",
        66,
        "Easy to do. We collapse them when the first token arrives and keep a summary line you can reopen.",
      ),
      said(
        "Diego Alvarez",
        118,
        "For the composer, voice should be the default button and swap to send while you type.",
      ),
    ],
    mindMap: topic(
      "Leo chat",
      topic("Agent steps", topic("Fold on answer"), topic("Summary line")),
      topic("Composer", topic("Voice by default"), topic("Single row")),
      topic("Full screen", topic("Smooth morph")),
    ),
  }),
];
