import type { DemoInsight } from "./demo-insight";

/** The emails that don't need the user now: worth knowing, or safe to set aside. */
export const laterInsights: DemoInsight[] = [
  {
    mail_id: "110e8400-e29b-11d4-a716-446655440000",
    triage: "fyi",
    summary:
      "Alice is happy with the project’s progress and left a few minor suggestions to go through at the next meeting.",
    key_points: ["Suggestions in project-notes.docx"],
    analyze_ms: 2500,
  },
  {
    mail_id: "8f7b5db9-d935-4e42-8e05-1f1d0a3dfb97",
    triage: "fyi",
    summary:
      "Michael will announce a change to the product launch plan at the next team meeting, based on feedback from beta testers.",
    key_points: ["Bring your insights to the team meeting"],
  },
  {
    mail_id: "de305d54-75b4-431b-adb2-eb6b9e546014",
    triage: "fyi",
    summary: "James registered for next month’s conference and can cover any sessions you’re interested in.",
    key_points: ["Conference schedule attached"],
  },
  {
    mail_id: "c1a0ecb4-2540-49c5-86f8-21e5ce79e4e6",
    triage: "fyi",
    summary: "The product launch is on track. William will share the details on the upcoming call.",
  },
  {
    mail_id: "ba54eefd-4097-4949-99f2-2a9ae4d1a836",
    triage: "fyi",
    summary: "Mia confirmed the travel itinerary and accommodation are in order and is open to activity tips.",
  },
  {
    mail_id: "d67c1842-7f8b-4b4b-9be1-1b3b1ab4611d",
    triage: "fyi",
    summary: "Finance approved the project budget, so the project can go ahead as planned.",
    key_points: ["Final budget attached"],
  },
  {
    mail_id: "2f0130cb-39fc-44c4-bb3c-0a4337edaaab",
    triage: "low",
    summary: "Olivia suggests a tropical trip next month and put together a few destinations. Personal, no deadline.",
  },
  {
    mail_id: "7dd90c63-00f6-40f3-bd87-5060a24e8ee7",
    triage: "low",
    summary: "Sophia’s team dinner was planned for the week after she wrote, so it has most likely already happened.",
  },
  {
    mail_id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    triage: "low",
    summary: "Ava shared the agenda for a meeting that has since taken place.",
  },
  {
    mail_id: "df09b6ed-28bd-4e0c-85a9-9320ec5179aa",
    triage: "low",
    summary: "Ethan floated a team-building event a few months ago. No date was set and the thread went quiet.",
  },
  {
    mail_id: "6c9a7f94-8329-4d70-95d3-51f68c186ae1",
    triage: "low",
    summary: "Samuel suggested a mountain hike months ago. The weekend he meant has long passed.",
  },
];
