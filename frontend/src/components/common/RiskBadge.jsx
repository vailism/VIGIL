import React from 'react';
import { getRiskBg } from '../../data/mockData';
export default function RiskBadge({ level, score, size = 'sm' }) {
  const classes = getRiskBg(level);
  const sizeClasses = { xs: 'text-[10px] px-2 py-0.5', sm: 'text-xs px-2.5 py-1', md: 'text-sm px-3 py-1.5', lg: 'text-base px-3.5 py-1.5' };
  return (
    <span className={`inline-flex items-center gap-1.5 font-semibold rounded-full border shadow-sm ${classes} ${sizeClasses[size]}`}>
      {score !== undefined && <span className="font-mono">{score}</span>}
      <span>{level}</span>
    </span>
  );
}
