import { useCallback, useEffect, useState } from 'react';

import { ReservationRecord } from '../../types';
import { fetchAppointments } from '../../api/appointments';

export function useReservationsStore() {
  const [reservations, setReservations] = useState<ReservationRecord[]>([]);
  const [loadingReservations, setLoadingReservations] = useState(false);

  const loadReservations = useCallback(async () => {
    setLoadingReservations(true);
    try {
      const data = await fetchAppointments();
      setReservations(data);
    } catch (error) {
      console.error('加载预约记录失败', error);
      setReservations([]);
    } finally {
      setLoadingReservations(false);
    }
  }, []);

  useEffect(() => {
    void loadReservations();
  }, [loadReservations]);

  return {
    reservations,
    loadingReservations,
    reloadReservations: loadReservations,
  };
}
