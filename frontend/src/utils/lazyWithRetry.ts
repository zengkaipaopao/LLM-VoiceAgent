import { ComponentType, lazy, LazyExoticComponent } from 'react';

const RELOAD_MARKER = 'llm-voice-desk:chunk-reload';

function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed') ||
    message.includes('Loading chunk')
  );
}

export function lazyWithRetry<T extends ComponentType<object>>(
  importer: () => Promise<{ default: T }>
): LazyExoticComponent<T> {
  return lazy(async () => {
    try {
      const module = await importer();
      sessionStorage.removeItem(RELOAD_MARKER);
      return module;
    } catch (error) {
      if (isChunkLoadError(error) && !sessionStorage.getItem(RELOAD_MARKER)) {
        sessionStorage.setItem(RELOAD_MARKER, '1');
        window.location.reload();
        return new Promise<never>(() => undefined);
      }
      sessionStorage.removeItem(RELOAD_MARKER);
      throw error;
    }
  });
}
