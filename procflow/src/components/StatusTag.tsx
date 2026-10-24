import type { ReactNode } from 'react';

type StatusTagProps = {
  children: ReactNode;
  tone?: 'cyan' | 'amber' | 'teal' | 'muted' | 'simulation';
  dot?: boolean;
};

export function StatusTag({ children, tone = 'muted', dot = false }: StatusTagProps) {
  return (
    <span className={`status-tag status-tag--${tone}`}>
      {dot && <span className="status-tag__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}
