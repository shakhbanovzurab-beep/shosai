"use client";

import type { ReactNode } from "react";

import { useFormStatus } from "react-dom";

import { Button } from "@/components/ui/button";

/** A form's submit button, disabled while its action runs; React tracks that and always lets go. */
export function SubmitButton({ children }: { children: ReactNode }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending} aria-busy={pending}>
      {children}
    </Button>
  );
}
