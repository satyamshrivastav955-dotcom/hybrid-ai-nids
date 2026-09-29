import { useEffect, useRef, useState } from 'react';
import { wsUrl } from '../services/api';

export function useWebSocket(onMessage: (m: unknown) => void) {
  const [connected, setConnected] = useState(false);
  const cb = useRef(onMessage);
  cb.current = onMessage;
  useEffect(() => {
    let ws: WebSocket | null = null;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const connect = () => {
      if (!alive) return;
      ws = new WebSocket(wsUrl());
      ws.onopen = () => setConnected(true);
      ws.onclose = () => { setConnected(false); timer = setTimeout(connect, 3000); };
      ws.onerror = () => ws?.close();
      ws.onmessage = (e) => { try { cb.current(JSON.parse(e.data)); } catch { /* ignore */ } };
    };
    connect();
    return () => { alive = false; clearTimeout(timer); ws?.close(); };
  }, []);
  return connected;
}

export function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    fn().then((d) => alive && setData(d)).catch((e) => alive && setError(String(e))).finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading, reload: () => fn().then(setData).catch((e) => setError(String(e))) };
}
