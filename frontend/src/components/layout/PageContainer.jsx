import React from 'react';
export default function PageContainer({ title, subtitle, children, actions }) {
  return (
    <div className="animate-fade-in space-y-5">
      {title && (
        <div className="panel-strong rounded-[1.75rem] px-5 sm:px-6 py-5 sm:py-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-3xl">
            <p className="text-[10px] uppercase tracking-[0.32em] text-navy-500 font-bold mb-2">VIGIL console</p>
            <h1 className="text-2xl sm:text-3xl font-bold text-navy-900 tracking-tight">{title}</h1>
            {subtitle && <p className="text-sm text-slate-600 mt-2 max-w-2xl">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
        </div>
      )}
      <div className="space-y-5">{children}</div>
    </div>
  );
}
