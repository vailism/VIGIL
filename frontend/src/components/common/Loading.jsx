import React from 'react';
import { Loader2 } from 'lucide-react';
export default function Loading({ message = 'Loading data...' }) {
  return (
    <div className="panel-strong rounded-[1.5rem] min-h-[320px] flex items-center justify-center px-6 py-10 text-slate-600">
      <div className="flex flex-col items-center text-center max-w-sm">
        <div className="w-12 h-12 rounded-2xl bg-navy-50 border border-navy-100 flex items-center justify-center mb-4">
          <Loader2 size={22} className="animate-spin text-navy-700" />
        </div>
        <p className="text-sm font-medium text-slate-700">{message}</p>
        <p className="text-[11px] text-slate-500 mt-1">Synchronizing the live backend and portfolio telemetry.</p>
      </div>
    </div>
  );
}
