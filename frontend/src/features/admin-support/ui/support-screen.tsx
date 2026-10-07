import { SupportInbox } from "./support-inbox";

/** Admin › Support: the full-height inbox, edge to edge; `initialTicket` opens that conversation. */
export function SupportScreen({ initialTicket }: { readonly initialTicket: string | null }) {
  return (
    <div data-content-padding="false">
      <h1 className="sr-only">Поддержка</h1>
      <SupportInbox initialTicket={initialTicket} />
    </div>
  );
}
