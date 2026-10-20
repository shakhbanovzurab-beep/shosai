export interface NoteParticipant {
  name: string;
  role: string;
  email: string;
}

/** Where the user's own notes were last edited: a desktop app during the meeting, or here on the web. */
export type NotesApp = "macos" | "windows" | "web";

/** What the user typed about the meeting themselves, in the desktop app or on its page here. */
export interface ManualNotes {
  app: NotesApp;
  /** ISO timestamp of the last edit. */
  updatedAt: string;
  /** Markdown: headings, bulleted and numbered lists, bold, italic and links. */
  text: string;
}

export interface NoteActionItem {
  id: string;
  text: string;
  owner: string;
  done: boolean;
}

export interface TranscriptLine {
  speaker: string;
  /** Seconds from the start of the recording. */
  at: number;
  text: string;
  /** Сколько секунд длилась реплика, если сервер это знает; иначе её длину оценивают по словам. */
  duration?: number;
}

/** Встреча, какой её выгружает расшифровка: название, начало, длительность, люди и реплики. */
export interface TranscriptDocument {
  id: string;
  title: string;
  startedAt: string;
  durationMinutes: number;
  participants: { name: string; role: string }[];
  transcript: TranscriptLine[];
}

export interface MindMapNode {
  label: string;
  children?: MindMapNode[];
}

export type NoteFolderColor = "red" | "blue" | "amber" | "green" | "violet";

export interface NoteFolder {
  id: string;
  name: string;
  color: NoteFolderColor;
}

export interface MeetingNote {
  id: string;
  title: string;
  folderId?: string;
  /** ISO timestamp of when the meeting started. */
  startedAt: string;
  durationMinutes: number;
  participants: NoteParticipant[];
  tags: string[];
  /** The user's own notes from the desktop app; absent when they didn't type any. */
  myNotes?: ManualNotes;
  summary: string;
  keyPoints: string[];
  decisions: string[];
  actionItems: NoteActionItem[];
  transcript: TranscriptLine[];
  mindMap: MindMapNode;
}
