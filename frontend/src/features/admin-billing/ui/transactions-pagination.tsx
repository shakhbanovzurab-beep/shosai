import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

import { formatInteger } from "../domain/format";

function pageWindow(current: number, count: number) {
  if (count <= 5) return Array.from({ length: count }, (_, index) => index + 1);
  const start = Math.min(Math.max(current - 2, 1), count - 4);
  return Array.from({ length: 5 }, (_, index) => start + index);
}

export function TransactionsPagination({
  page,
  pageCount,
  total,
  disabled,
  onPage,
}: {
  page: number;
  pageCount: number;
  total: number;
  disabled: boolean;
  onPage: (page: number) => void;
}) {
  return (
    <nav
      aria-label="Страницы платежей"
      className="flex flex-col gap-3 px-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="text-muted-foreground text-sm tabular-nums">
        Страница {formatInteger(page)} из {formatInteger(pageCount)} · всего {formatInteger(total)}
      </p>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Предыдущая страница"
          disabled={disabled || page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft />
        </Button>
        {pageWindow(page, pageCount).map((number) => (
          <Button
            key={number}
            variant={number === page ? "outline" : "ghost"}
            size="icon-sm"
            className="w-auto min-w-7 px-1.5 tabular-nums"
            aria-label={`Страница ${number}`}
            aria-current={number === page ? "page" : undefined}
            disabled={disabled}
            onClick={() => onPage(number)}
          >
            {number}
          </Button>
        ))}
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Следующая страница"
          disabled={disabled || page >= pageCount}
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight />
        </Button>
      </div>
    </nav>
  );
}
