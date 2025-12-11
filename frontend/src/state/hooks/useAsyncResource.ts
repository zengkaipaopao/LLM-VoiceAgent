import { Dispatch, SetStateAction, useCallback, useEffect, useRef, useState } from 'react';

type UseAsyncResourceOptions<T> = {
  initialValue: T;
  onError?: (error: unknown) => void;
  auto?: boolean;
};

type AsyncResourceResult<T> = {
  data: T;
  setData: Dispatch<SetStateAction<T>>;
  loading: boolean;
  reload: () => Promise<T>;
  loaded: boolean;
};

export function useAsyncResource<T>(
  fetcher: () => Promise<T>,
  { initialValue, onError, auto = true }: UseAsyncResourceOptions<T>,
): AsyncResourceResult<T> {
  const initialRef = useRef(initialValue);
  const errorHandlerRef = useRef(onError);
  useEffect(() => {
    errorHandlerRef.current = onError;
  }, [onError]);
  const [data, setData] = useState<T>(() => initialRef.current);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const loadedRef = useRef(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetcher();
      setData(result);
       loadedRef.current = true;
       setLoaded(true);
      return result;
    } catch (error) {
      errorHandlerRef.current?.(error);
      if (!loadedRef.current) {
        setData(initialRef.current);
      }
      throw error;
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    if (!auto) {
      return;
    }
    void reload();
  }, [auto, reload]);

  return { data, setData, loading, reload, loaded };
}
