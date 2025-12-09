import { useAsyncResource } from '../hooks/useAsyncResource';

import { ReservationRecord } from '../../types';
import { fetchAppointments } from '../../api/appointments';

export function useReservationsStore() {
  const {
    data: reservations,
    loading: loadingReservations,
    reload: reloadReservations,
  } = useAsyncResource<ReservationRecord[]>(fetchAppointments, {
    initialValue: [],
    onError: (error) => console.error('加载预约记录失败', error),
  });

  return {
    reservations,
    loadingReservations,
    reloadReservations,
  };
}
