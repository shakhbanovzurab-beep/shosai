import { describe, expect, it } from "vitest";

import { checkImport } from "./import-rules";

const problemsOf = (file: string, specifier: string) => {
  const problems: string[] = [];
  const edges: string[] = [];
  checkImport(
    file,
    specifier,
    (message) => problems.push(message),
    (to) => edges.push(to),
  );
  return { problems, edges };
};

describe("checkImport", () => {
  it("lets ui use its slice's model and another slice's ui, recording the slice edge", () => {
    expect(problemsOf("src/features/notes/ui/a.tsx", "../model/b").problems).toEqual([]);
    expect(problemsOf("src/features/notes/ui/a.tsx", "@/features/hub/ui/chip")).toEqual({
      problems: [],
      edges: ["hub"],
    });
  });

  it("keeps mocks out of everything but the mocks", () => {
    expect(problemsOf("src/features/notes/ui/a.tsx", "@/features/hub/mocks/store").problems).toHaveLength(1);
    expect(problemsOf("src/app/pages/user/a.tsx", "@/mocks/runtime").problems).toHaveLength(1);
    expect(problemsOf("src/features/hub/mocks/a.ts", "@/features/notes/mocks/b").problems).toEqual([]);
    expect(problemsOf("src/features/hub/ui/a.tsx", "msw").problems).toHaveLength(1);
  });

  it("keeps the pure layers free of frameworks, UI and other slices", () => {
    expect(problemsOf("src/features/notes/domain/a.ts", "react").problems).toHaveLength(1);
    expect(problemsOf("src/features/notes/api/a.ts", "@/components/ui/button").problems).toHaveLength(1);
    expect(problemsOf("src/features/notes/domain/a.ts", "@/features/hub/domain/b").problems).toHaveLength(1);
    expect(problemsOf("src/features/notes/api/a.ts", "@/lib/api/request").problems).toEqual([]);
  });

  it("forbids routing from slices, shared code reaching features, and Next.js", () => {
    expect(problemsOf("src/features/notes/ui/a.tsx", "@/app/root/page-meta").problems).toHaveLength(1);
    expect(problemsOf("src/components/a.tsx", "@/features/notes/ui/b").problems).toHaveLength(1);
    expect(problemsOf("src/lib/a.ts", "next/link").problems).toHaveLength(1);
  });

  it("follows the order of layers inside a slice", () => {
    expect(problemsOf("src/features/notes/model/a.ts", "../ui/b").problems).toHaveLength(1);
    expect(problemsOf("src/features/notes/ui/a.tsx", "../api/b").problems).toHaveLength(1);
  });
});
