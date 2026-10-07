/** The one-line explanation at the top of each Studio tab. */
export function TabIntro({ children }: { children: React.ReactNode }) {
  return <p className="max-w-3xl text-muted-foreground text-sm">{children}</p>;
}
