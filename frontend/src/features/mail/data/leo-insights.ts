import type { DemoInsight } from "./demo-insight";
import { laterInsights } from "./leo-insights-later";

/** The emails waiting on the user. Leo drafts a reply wherever it can; feedback needs the user's own judgement. */
export const demoInsights: DemoInsight[] = [
  {
    mail_id: "6c84fb90-12c4-11e1-840d-7b25c5ee775a",
    triage: "needs_you",
    next_step: "Confirm a time for tomorrow’s project meeting",
    summary:
      "William wants to meet tomorrow to align on the project’s next steps and asks you to come with questions and ideas. No time has been set yet.",
    key_points: ["Meeting tomorrow, no time agreed yet", "Design file, feature list and preview attached"],
    reply_in_days: 0,
    draft:
      "Hi William,\n\nTomorrow works for me. How about 11:00? I’ll go through the design file and the feature list beforehand and bring my questions.\n\nIf 11:00 doesn’t suit you, just suggest another time.\n\nBest,\nArham",
    analyze_ms: 4500,
  },
  {
    mail_id: "61c35085-72d7-42b4-8d62-738f700d4b92",
    triage: "needs_you",
    next_step: "Answer Emily’s question about the budget discrepancy",
    summary:
      "Emily found a discrepancy in how resources are allocated in the project budget and suggests savings that wouldn’t affect quality.",
    key_points: ["Her analysis is in budget-analysis.docx", "She wants to go through it at the next meeting"],
    reply_in_days: 1,
    draft:
      "Hi Emily,\n\nThanks for flagging this and for the detailed analysis. I’ll go through it today. Let’s put the budget first on the agenda for our next meeting so we can agree on the changes.\n\nBest,\nArham",
  },
  {
    mail_id: "3e7c3f6d-bdf5-46ae-8d90-171300f27ae2",
    triage: "needs_you",
    next_step: "Let Bob know if you’re in for the weekend hike",
    summary: "Bob is planning a hike in the nearby mountains this weekend and asks whether you’d like to join.",
    reply_in_days: 2,
    draft:
      "Hey Bob,\n\nCount me in, a hike sounds great. Send me the route you have in mind and we’ll sort out the details.\n\nArham",
  },
  {
    mail_id: "1f0f2c02-e299-40de-9b1d-86ef9e42126b",
    triage: "needs_you",
    next_step: "Review Sarah’s revised proposal and send comments",
    summary:
      "Sarah’s team revised the proposal based on your feedback and is waiting for any further comments before moving ahead.",
    key_points: ["Revised layout in proposal-layout.fig"],
    reply_in_days: 3,
    draft:
      "Hi Sarah,\n\nThanks to you and the team for the quick turnaround. I’ll review the revised layout and send my comments by the end of the week.\n\nBest,\nArham",
  },
  {
    mail_id: "17c0a96d-4415-42b1-8b4f-764efab57f66",
    triage: "needs_you",
    next_step: "Set up a meeting with David about his project idea",
    summary:
      "David proposes expanding into a fast-growing niche market and has a detailed proposal ready. He asked to meet over a week ago and hasn’t heard back.",
    key_points: ["Waiting on you for over a week", "Proposal ready to share"],
    reply_in_days: -1,
    draft:
      "Hi David,\n\nSorry for the slow reply, this sounds promising. Could you send over the proposal? I’m free on Thursday or Friday afternoon to go through it together. Let me know what suits you.\n\nBest,\nArham",
  },
  {
    mail_id: "99a88f78-3eb4-4d87-87b7-7b15a49a0a05",
    triage: "needs_you",
    next_step: "Review Daniel’s deliverables and share your feedback",
    summary:
      "Daniel asked for your feedback on the latest project deliverables, especially where quality or efficiency could improve.",
    key_points: ["Waiting on you for about a month"],
  },
  ...laterInsights,
];
