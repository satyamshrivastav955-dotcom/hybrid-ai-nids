import { useEffect } from 'react';

/** Global key shortcuts; ignored while typing in inputs. Keys: single chars, '/' supported. */
export function useShortcuts(map: Record<string, (e: KeyboardEvent) => void>) {
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      const h = map[e.key];
      if (h) { e.preventDefault(); h(e); }
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(Object.keys(map))]);
}
