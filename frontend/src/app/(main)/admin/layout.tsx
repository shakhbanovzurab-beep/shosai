import type { ReactNode } from "react";

import type { Metadata } from "next";

import { PanelLayout } from "@/features/shell";

export const metadata: Metadata = {
  robots: {
    index: false,
    follow: false,
  },
};

export default function Layout({ children }: Readonly<{ children: ReactNode }>) {
  return <PanelLayout panel="admin">{children}</PanelLayout>;
}
