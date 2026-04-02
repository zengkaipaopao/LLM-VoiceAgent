import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  AppointmentsDataTable,
  AppointmentsPromptSelector,
} from '../components/organisms/Appointments';
import { AppointmentDetailModal } from '../components/organisms/AppointmentDetailModal/AppointmentDetailModal';
import { PageTemplate } from '../components/templates/PageTemplate';
import { useAppointmentsPage } from '../hooks/useAppointmentsPage';
import { Appointment } from '../types/shared';

export function Appointments() {
  const { t } = useTranslation(['pages', 'common']);
  const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);

  const {
    availablePrompts,
    selectedPromptId,
    setSelectedPromptId,
    loading,
    page,
    setPage,
    pageSize,
    setPageSize,
    total,
    setSearchQuery,
    selectedFilters,
    setSelectedFilters,
    headers,
    tableRows,
    refreshAppointments,
  } = useAppointmentsPage((key) => t(key));

  const hasActiveFilters = useMemo(
    () => Object.values(selectedFilters).some((value) => Array.isArray(value) && value.length > 0),
    [selectedFilters]
  );

  const openAppointmentDetails = (appointment: Appointment) => {
    setSelectedAppointment(appointment);
    setDetailModalOpen(true);
  };

  const clearFilters = () => {
    setSelectedFilters({});
    setSearchQuery('');
  };

  const handlePromptChange = (promptId: string) => {
    setSelectedPromptId(promptId);
    setPage(1);
  };

  return (
    <PageTemplate title={t('pages:appointments.title')} subtitle={t('pages:appointments.subtitle')}>
      <AppointmentsPromptSelector
        availablePrompts={availablePrompts}
        selectedPromptId={selectedPromptId}
        onPromptChange={handlePromptChange}
        titleText={t('pages:appointments.promptSelector.title')}
        label={t('pages:appointments.promptSelector.label')}
      />

      <AppointmentsDataTable
        rows={tableRows}
        headers={headers}
        loading={loading}
        totalItems={total}
        page={page}
        pageSize={pageSize}
        selectedFilters={selectedFilters}
        hasActiveFilters={hasActiveFilters}
        onSearch={setSearchQuery}
        onFilterChange={setSelectedFilters}
        onClearFilters={clearFilters}
        onPageChange={(nextPage, nextPageSize) => {
          setPage(nextPage);
          setPageSize(nextPageSize);
        }}
        onRefresh={refreshAppointments}
        onViewAppointment={openAppointmentDetails}
        t={(key) => t(key)}
      />

      <AppointmentDetailModal
        open={detailModalOpen}
        onClose={() => setDetailModalOpen(false)}
        onSuccess={refreshAppointments}
        appointment={selectedAppointment}
      />
    </PageTemplate>
  );
}
