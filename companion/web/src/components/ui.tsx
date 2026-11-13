import { CaretDownIcon, CheckCircleIcon, HourglassIcon, MinusCircleIcon, XCircleIcon } from '@phosphor-icons/react';
import type { Semantic } from '../tones';
import type { ReadStatus, RowStatus } from '../wire';

/** Status is never colour alone: each status has its own icon shape and a word. */
export function StatusIcon({ status, size = 14 }: { status: ReadStatus | RowStatus; size?: number }) {
  const props = { size, weight: 'regular' as const, 'aria-hidden': true };
  switch (status) {
    case 'confirmed':
    case 'pass':
      return <CheckCircleIcon {...props} />;
    case 'failed':
    case 'fail':
      return <XCircleIcon {...props} />;
    case 'waiting':
    case 'na':
      return <HourglassIcon {...props} />;
    case 'not_applicable':
      return <MinusCircleIcon {...props} />;
  }
}

export const toneClass = (tone: Semantic | 'text') => `tone-${tone}`;

interface SelectProps {
  label: string;
  value: string;
  options: readonly string[];
  disabled?: boolean;
  onChange: (value: string) => void;
}

/** A native <select> under a styled face: full keyboard and screen reader support for free. */
export function Select({ label, value, options, disabled, onChange }: SelectProps) {
  const list = options.includes(value) || !value ? options : [value, ...options];
  return (
    <label className={`select${disabled ? ' is-disabled' : ''}`}>
      <span className="select-label">{label}</span>
      <span className="select-value mono">{value || '-'}</span>
      <CaretDownIcon size={12} aria-hidden className="select-caret" />
      <select aria-label={label} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        {list.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Skeleton({ w, h, className = '' }: { w?: number | string; h: number; className?: string }) {
  return <span className={`skeleton ${className}`} style={{ width: w ?? '100%', height: h }} aria-hidden />;
}
