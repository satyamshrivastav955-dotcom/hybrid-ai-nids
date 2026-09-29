/** Minimal outline icon set (single style, currentColor, 16px). */
import React from 'react';

const P: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <svg width={16} height={16} viewBox="0 0 16 16" fill="none" stroke="currentColor"
    strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden>{children}</svg>
);

export const I = {
  dashboard: <P><rect x={2} y={2} width={5} height={5} rx={1} /><rect x={9} y={2} width={5} height={5} rx={1} /><rect x={2} y={9} width={5} height={5} rx={1} /><rect x={9} y={9} width={5} height={5} rx={1} /></P>,
  traffic: <P><path d="M1 8h3l2-5 3 10 2-5h4" /></P>,
  alerts: <P><path d="M3 13V8l5-5 5 5v5" /><path d="M2 13h12" /></P>,
  attacks: <P><circle cx={8} cy={8} r={5.5} /><circle cx={8} cy={8} r={1.4} /></P>,
  network: <P><circle cx={3.5} cy={8} r={1.8} /><circle cx={12.5} cy={4} r={1.8} /><circle cx={12.5} cy={12} r={1.8} /><path d="M5.2 7.2 10.8 4.7M5.2 8.8l5.6 2.5" /></P>,
  drift: <P><path d="M1 12c2.5 0 2.5-8 5-8s2.5 8 5 8 2.5-5 4-5" /></P>,
  models: <P><path d="M2 13V9M6 13V5M10 13V7M14 13V3" /></P>,
  intel: <P><circle cx={8} cy={8} r={5.5} /><path d="M8 5.5v2.5l1.8 1.8" /></P>,
  reports: <P><path d="M4 1.5h6L13 5v9.5H4z" /><path d="M10 1.5V5h3M6.5 8h4M6.5 10.5h4" /></P>,
  system: <P><circle cx={8} cy={8} r={2} /><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2 3.4 12.6" /></P>,
  settings: <P><path d="M2 5h4l1.5-2h3L12 5h2v6h-2l-1.5 2h-3L6 11H2z" /><circle cx={8} cy={8} r={1.6} /></P>,
};
export type IconName = keyof typeof I;
