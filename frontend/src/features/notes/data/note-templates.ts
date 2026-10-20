import type { SampleTemplate } from "../domain/templates";

// Шаблоны, что поставляет продукт, по их кодам: API отдаёт их этими кодами (`builtin`), а кабинет называет их
// и их заголовки на языке человека по каталогу `notesTemplates`. Коды совпадают с кодами бэкенда.
export const SAMPLE_TEMPLATES = [
  {
    id: "catchUpInvestor",
    icon: "handshake",
    sections: [
      ["summary", "whereWeAre"],
      ["keyPoints", "updatesShared"],
      ["decisions", "whatWeAgreed"],
      ["actionItems", "followUps"],
    ],
  },
  {
    id: "catchUpPortfolio",
    icon: "chart",
    sections: [
      ["summary", "companyUpdate"],
      ["keyPoints", "metricsAndHighlights"],
      ["actionItems", "howWeCanHelp"],
    ],
  },
  {
    id: "lpProspective",
    icon: "magnet",
    sections: [
      ["summary", "overview"],
      ["keyPoints", "theirInterests"],
      ["actionItems", "nextSteps"],
    ],
  },
  {
    id: "vcBoardMeeting",
    icon: "briefcase",
    sections: [
      ["summary", "boardSummary"],
      ["keyPoints", "discussion"],
      ["decisions", "resolutions"],
      ["actionItems", "ownersAndDeadlines"],
    ],
  },
  {
    id: "vcPitch",
    icon: "rocket",
    sections: [
      ["summary", "thePitch"],
      ["keyPoints", "whatStoodOut"],
      ["decisions", "verdict"],
      ["actionItems", "diligenceToDos"],
    ],
  },
  {
    id: "oneOnOne",
    icon: "users",
    sections: [
      ["summary", "howItsGoing"],
      ["keyPoints", "topics"],
      ["actionItems", "nextSteps"],
    ],
  },
  {
    id: "customerCall",
    icon: "phone",
    sections: [
      ["summary", "context"],
      ["keyPoints", "painsAndRequests"],
      ["decisions", "outcome"],
      ["actionItems", "followUps"],
    ],
  },
  {
    id: "teamSync",
    icon: "calendar",
    sections: [
      ["keyPoints", "updates"],
      ["decisions", "decisions"],
      ["actionItems", "whoDoesWhat"],
    ],
  },
] as const satisfies readonly SampleTemplate[];

export type SampleTemplateId = (typeof SAMPLE_TEMPLATES)[number]["id"];
export type SampleHeading = (typeof SAMPLE_TEMPLATES)[number]["sections"][number][1];
