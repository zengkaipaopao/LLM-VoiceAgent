import { useTranslation } from 'react-i18next';

import { CallDetailsModal, CallsDataTable } from '../components/organisms/Calls';
import { PageTemplate } from '../components/templates/PageTemplate';
import { useCallsPage } from '../hooks/useCallsPage';

const EMPTY_CALL_FILTERS = {
  status: [],
  handler_type: [],
};

export function Calls() {
  const { t } = useTranslation(['pages', 'common']);
  const {
    loading,
    page,
    setPage,
    pageSize,
    setPageSize,
    total,
    selectedFilters,
    setSelectedFilters,
    hasActiveFilters,
    setSearchQuery,
    tableRows,
    refreshCalls,
    selectedCall,
    openCallDetails,
    closeCallDetails,
    detailModalOpen,
    linkedAppointmentId,
    loadingLinkedAppointment,
  } = useCallsPage();

  return (
    <PageTemplate title={t('calls.title')} subtitle={t('calls.subtitle')}>
      <CallsDataTable
        rows={tableRows}
        loading={loading}
        totalItems={total}
        page={page}
        pageSize={pageSize}
        selectedFilters={selectedFilters}
        hasActiveFilters={hasActiveFilters}
        onSearch={setSearchQuery}
        onFilterChange={setSelectedFilters}
        onClearFilters={() => setSelectedFilters(EMPTY_CALL_FILTERS)}
        onPageChange={(nextPage, nextPageSize) => {
          setPage(nextPage);
          setPageSize(nextPageSize);
        }}
        onRefresh={refreshCalls}
        onViewCall={openCallDetails}
        t={(key) => t(key)}
      />

      <CallDetailsModal
        open={detailModalOpen}
        onClose={closeCallDetails}
        selectedCall={selectedCall}
        linkedAppointmentId={linkedAppointmentId}
        loadingLinkedAppointment={loadingLinkedAppointment}
        t={(key) => t(key)}
      />
    </PageTemplate>
  );
}
