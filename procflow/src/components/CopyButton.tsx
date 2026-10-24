import { useState } from 'react';
import { Check, Copy, TriangleAlert } from 'lucide-react';

type CopyState = 'idle' | 'copied' | 'error';

export function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<CopyState>('idle');

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState('copied');
      window.setTimeout(() => setState('idle'), 1600);
    } catch {
      setState('error');
    }
  }

  const label = state === 'copied' ? 'Copied' : state === 'error' ? 'Copy unavailable' : 'Copy';
  return (
    <button className={`copy-button${state === 'error' ? ' copy-button--error' : ''}`} type="button" onClick={copy} aria-label={label} aria-live="polite">
      {state === 'copied' ? <Check size={14} aria-hidden="true" /> : state === 'error' ? <TriangleAlert size={13} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      {label}
    </button>
  );
}
