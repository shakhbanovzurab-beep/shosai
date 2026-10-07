/*
 * The demo's own task list. Titles and tags are what the user wrote, so they stay as written in every
 * interface language; times are times of day, shown in the interface language.
 */

export type Task = {
  id: string;
  title: string;
  tag: string | null;
  /** Time of day, "HH:mm" (24-hour); null for a task without a time. */
  time: string | null;
  checked: boolean;
};

const task = (id: string, title: string, tag: string | null, time: string | null, checked = false): Task => ({
  id,
  title,
  tag,
  time,
  checked,
});

export const tasks: Task[] = [
  task("t1", "Finalize Q2 roadmap", "Work", "10:00"),
  task("t2", "Review design system updates", "Design", "11:30", true),
  task("t3", "Reply to important emails", "Admin", "14:00"),
  task("t4", "Plan creator content for this week", "Content", "16:30"),
  task("t5", "Prepare weekly team sync notes", "Planning", "18:00"),
];
