"use client";

import { Link } from "@/lib/navigation";

import type { MdInline } from "../../domain/markdown";
import { CitedText } from "./citations";

/** Строка ответа: выделения, код, ссылки и маркеры источников; путь кабинета открывается без перезагрузки. */
export function MdInlines({ nodes }: { readonly nodes: readonly MdInline[] }) {
  return nodes.map((node) => <MdInlineNode key={node.key} node={node} />);
}

function MdInlineNode({ node }: { readonly node: MdInline }) {
  switch (node.type) {
    case "text":
      return <CitedText text={node.text} />;
    case "strong":
      return (
        <strong className="font-semibold">
          <MdInlines nodes={node.children} />
        </strong>
      );
    case "em":
      return (
        <em>
          <MdInlines nodes={node.children} />
        </em>
      );
    case "del":
      return (
        <del>
          <MdInlines nodes={node.children} />
        </del>
      );
    case "code":
      return <code className="rounded-sm bg-muted px-1 py-0.5 font-mono text-[0.85em]">{node.text}</code>;
    case "br":
      return <br />;
    case "link":
      return node.href.startsWith("/") ? (
        <Link href={node.href} className="font-medium underline underline-offset-2">
          <MdInlines nodes={node.children} />
        </Link>
      ) : (
        <a
          href={node.href}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium underline underline-offset-2"
        >
          <MdInlines nodes={node.children} />
        </a>
      );
  }
}
