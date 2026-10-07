"use client";
import type { MouseEvent } from "react";

import type { ReactTable } from "@tanstack/react-table";

import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import type { DataTableFeatures } from "@/lib/data-table-features";

import type { OpportunityRow } from "../../domain/crm/opportunity";

function preventPaginationNavigation(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
}

function getPageNumbers(currentPage: number, pageCount: number) {
  if (pageCount <= 3) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }

  if (currentPage <= 2) return [1, 2, 3];
  if (currentPage >= pageCount - 1) return [pageCount - 2, pageCount - 1, pageCount];

  return [currentPage - 1, currentPage, currentPage + 1];
}

export function OpportunitiesPagination({ table }: { table: ReactTable<DataTableFeatures, OpportunityRow> }) {
  const currentPage = table.state.pagination.pageIndex + 1;
  const pageCount = table.getPageCount();
  const pageNumbers = getPageNumbers(currentPage, pageCount);

  return (
    <Pagination aria-label="Пагинация сделок" className="mx-0 w-auto justify-end">
      <PaginationContent className="gap-1.5">
        <PaginationItem>
          <PaginationPrevious
            aria-label="Предыдущая страница"
            text="Назад"
            href="#"
            className={!table.getCanPreviousPage() ? "pointer-events-none opacity-50" : undefined}
            onClick={(event) => {
              preventPaginationNavigation(event);
              table.previousPage();
            }}
          />
        </PaginationItem>
        {pageNumbers[0] > 1 ? (
          <PaginationItem>
            <PaginationEllipsis />
          </PaginationItem>
        ) : null}
        {pageNumbers.map((pageNumber) => (
          <PaginationItem key={`page-${pageNumber}`}>
            <PaginationLink
              href="#"
              isActive={table.state.pagination.pageIndex === pageNumber - 1}
              onClick={(event) => {
                preventPaginationNavigation(event);
                table.setPageIndex(pageNumber - 1);
              }}
            >
              {pageNumber}
            </PaginationLink>
          </PaginationItem>
        ))}
        {pageNumbers[pageNumbers.length - 1] < pageCount ? (
          <PaginationItem>
            <PaginationEllipsis />
          </PaginationItem>
        ) : null}
        <PaginationItem>
          <PaginationNext
            aria-label="Следующая страница"
            text="Далее"
            href="#"
            className={!table.getCanNextPage() ? "pointer-events-none opacity-50" : undefined}
            onClick={(event) => {
              preventPaginationNavigation(event);
              table.nextPage();
            }}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
}
