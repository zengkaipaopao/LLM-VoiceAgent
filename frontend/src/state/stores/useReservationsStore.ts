import { useCallback } from 'react';

import { fetchAppointments } from '../../api/appointments';
import { ReservationRecord } from '../../types';
import { useAsyncResource } from '../hooks/useAsyncResource';

export function useReservationsStore() {
  const {
    data: reservations,
    loading: loadingReservations,
    reload: reloadReservations,
    loaded: reservationsLoaded,
  } = useAsyncResource<ReservationRecord[]>(fetchAppointments, {
    initialValue: [],
    onError: (error) => console.error('加载预约记录失败', error),
    auto: false,
  });

  const loadReservations = useCallback(async () => {
    await reloadReservations();
  }, [reloadReservations]);

  return {
    reservations,
    loadingReservations,
    reloadReservations: loadReservations,
    reservationsLoaded,
  };
}
