import { describe, expect, it } from "vitest";

import type { MeetingCard } from "@/features/notes/domain/library";

import { meetingStatus } from "../domain/meeting";
import { meetingOfRecording } from "./meetings-resource";

const card = (patch: Partial<MeetingCard>): MeetingCard => ({
  id: "m-1",
  title: "Weekly sync",
  status: "completed",
  source: "live",
  startedAt: "2026-10-21T08:00:00Z",
  durationMinutes: 45,
  owned: true,
  participantNames: ["Anna", "Boris"],
  participantCount: 2,
  summary: "We agreed on the launch date.",
  keyPoints: [],
  firstDecision: null,
  actionItems: 3,
  notes: "ready",
  ...patch,
});

// Шесть часов спустя: запись, которую не закончили, всё ещё идёт, сколько бы ни длилась по часам.
const LATER = Date.parse("2026-10-21T14:00:00Z");

describe("recordings in Meetings", () => {
  it("shows a finished recording as past with Leo's recap and its tasks", () => {
    const meeting = meetingOfRecording(card({}));

    expect(meetingStatus(meeting, LATER)).toBe("past");
    expect(meeting.recap).toEqual({
      noteId: "m-1",
      summary: "We agreed on the launch date.",
      tasks: 3,
      decisions: null,
    });
    expect(meeting.source).toBe("recording");
    expect(meeting.end).toBe("2026-10-21T08:45:00.000Z");
  });

  it("keeps a recording live until it ends and waits for its notes", () => {
    const live = meetingOfRecording(card({ status: "active", notes: "processing", summary: null }));
    const writing = meetingOfRecording(card({ notes: "processing", source: "import" }));

    expect(meetingStatus(live, LATER)).toBe("live");
    expect(live.recording).toEqual({ noteId: "m-1", live: true, busy: true });
    expect(writing.recap).toBeNull();
    expect(writing.recording?.busy).toBe(true);
    expect(writing.source).toBe("upload");
  });
});
