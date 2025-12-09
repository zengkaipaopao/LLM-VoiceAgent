import { Dispatch, SetStateAction, useCallback, useEffect, useRef, useState } from 'react';

type UseAsyncResourceOptions<T> = {
  initialValue: T;
  onError?: (error: unknown) => void;
};

type AsyncResourceResult<T> = {
  data: T;
  setData: Dispatch<SetStateAction<T>>;
  loading: boolean;
  reload: () => Promise<T>;
};

export function useAsyncResource<T>(
  fetcher: () => Promise<T>,
  { initialValue, onError }: UseAsyncResourceOptions<T>,
): AsyncResourceResult<T> {
  const initialRef = useRef(initialValue);
  const errorHandlerRef = useRef(onError);
  useEffect(() => {
    errorHandlerRef.current = onError;
  }, [onError]);
  const [data, setData] = useState<T>(() => initialRef.current);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetcher();
      setData(result);
      return result;
    } catch (error) {
      errorHandlerRef.current?.(error);
      setData(initialRef.current);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, setData, loading, reload };
}
