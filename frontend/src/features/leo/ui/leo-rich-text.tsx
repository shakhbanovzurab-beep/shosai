import { Fragment } from "react";

// Minimal formatting for Leo's answers: paragraphs separated by blank lines, line breaks, and **bold**.
// Swap for a full Markdown renderer once real model output needs lists, links or code.
export function LeoRichText({ text }: { readonly text: string }) {
  const paragraphs = text.split(/\n{2,}/);

  return (
    <div className="flex flex-col gap-3">
      {paragraphs.map((paragraph, paragraphIndex) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: paragraphs only grow at the end while streaming
        <p key={paragraphIndex} dir="auto" className="whitespace-pre-wrap">
          {paragraph.split(/(\*\*[^*]+\*\*)/g).map((part, partIndex) =>
            part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
              // biome-ignore lint/suspicious/noArrayIndexKey: parts are derived from static text
              <strong key={partIndex} className="font-semibold">
                {part.slice(2, -2)}
              </strong>
            ) : (
              // biome-ignore lint/suspicious/noArrayIndexKey: parts are derived from static text
              <Fragment key={partIndex}>{part}</Fragment>
            ),
          )}
        </p>
      ))}
    </div>
  );
}
