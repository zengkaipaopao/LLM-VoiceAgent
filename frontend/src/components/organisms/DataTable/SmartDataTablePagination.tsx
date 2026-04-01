import { Pagination } from '@carbon/react';

interface SmartDataTablePaginationProps {
  page: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number, pageSize: number) => void;
}

export function SmartDataTablePagination({
  page,
  pageSize,
  totalItems,
  onPageChange,
}: SmartDataTablePaginationProps) {
  return (
    <Pagination
      backwardText="Previous page"
      forwardText="Next page"
      itemsPerPageText="Items per page:"
      page={page}
      pageSize={pageSize}
      pageSizes={[10, 20, 50, 100]}
      totalItems={totalItems}
      onChange={(event: { page: number; pageSize: number }) =>
        onPageChange(event.page, event.pageSize)
      }
    />
  );
}
