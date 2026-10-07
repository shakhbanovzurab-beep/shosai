import type { ManualNotes } from "../domain/types";
import { typed } from "./demo-meetings";

// Sample data until the desktop apps sync notes for real: what the user typed during some meetings.
// Meetings missing here had no notes of the user's own.
export const sampleMyNotes: Record<string, ManualNotes> = {
  "q4-roadmap-review": typed(
    "macos",
    "2026-10-05T09:52:00Z",
    `# Q4 priorities
- Leo agent backend = #1 for October
  - Maya: weekly milestones by Fri
- Notes needs transcript search + mind maps before beta
- mobile parity → Q1 (agreed, protects agent timeline)

# Beta
- 50 customers, mid-Nov
- behind a flag, Nov 16
- Priya: success metrics — task completion, time saved / week

check with Diego on mind map layouts next week`,
  ),
  "leo-design-critique": typed(
    "windows",
    "2026-10-02T15:08:00Z",
    `- agent steps = trust, but they fight the answer
  - fold them away once the answer starts?
- composer: one row until text wraps
- voice mode as default action in empty composer (like ChatGPT)
- full screen: morph, not a jump

ask Diego for the morph prototype`,
  ),
  "one-on-one-maya": typed(
    "macos",
    "2026-10-04T15:31:00Z",
    `# Growth
- wants group manager role in 2027
- stretch project: owns the Leo beta launch end to end

# Support from me
- intro to Elena for the launch comms
- monthly check-in on the launch plan`,
  ),
  "customer-interview-northwind": typed(
    "macos",
    "2026-09-30T16:44:00Z",
    `Liam — Head of Ops, ~30 internal meetings / week

# Pain
- decisions get lost between chat, email, docs
- nobody owns follow-ups

# Wants
- searchable transcripts
- weekly digest of action items (asked twice!)
- auto follow-up emails → would pay for this

add Northwind to beta list`,
  ),
  "pricing-workshop": typed(
    "windows",
    "2026-10-01T12:05:00Z",
    `# Seats vs usage
- Sales: seats, easier to forecast
- data: heavy users churn on usage pricing
  - top 10% of accounts = most agent minutes

# Plan
- test seat plan + agent-minutes add-on`,
  ),
  "romashka-sync-1003": typed(
    "macos",
    "2026-10-03T10:36:00Z",
    `- final pilot user list is in
- SSO is the last blocker before admin testing
  - Ivan: Romashka SSO access by Monday`,
  ),
  "meeting-oct-05-1718": typed(
    "macos",
    "2026-10-05T17:29:00Z",
    `Olga called about rollout
- admins still waiting on SSO
- want to start testing tomorrow
- check status with Ivan tonight`,
  ),
};
