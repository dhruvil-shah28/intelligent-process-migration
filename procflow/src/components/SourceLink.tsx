import { FileCode2 } from 'lucide-react';
import { sourceLabel, type SourceRef } from '../project-data';

type SourceLinkProps = {
  source: SourceRef;
  compact?: boolean;
};

export function SourceLink({ source, compact = false }: SourceLinkProps) {
  return (
    <span className={`source-link${compact ? ' source-link--compact' : ''}`}>
      <FileCode2 size={14} aria-hidden="true" />
      <span>{sourceLabel(source)}{!compact && <small>{source.summary}</small>}</span>
    </span>
  );
}
