export function toWebSocketBase(httpBaseUrl: string): string {
  if (httpBaseUrl.startsWith('https://')) return `wss://${httpBaseUrl.slice('https://'.length)}`;
  if (httpBaseUrl.startsWith('http://')) return `ws://${httpBaseUrl.slice('http://'.length)}`;

  const normalizedPath = httpBaseUrl.startsWith('/') ? httpBaseUrl : `/${httpBaseUrl}`;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${normalizedPath}`;
}
