import React from 'react';
import { Inbox } from 'lucide-react';
export default function EmptyState({ message = 'No data found', description = 'Try adjusting your filters.' }) {
  return (
    <div className="panel rounded-[1.5rem] flex flex-col items-center justify-center py-16 px-6 text-slate-500 text-center">
      <div className="w-14 h-14 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center mb-4 text-slate-400">
        <Inbox size={28} />
      </div>
      <p className="text-base font-semibold text-slate-700">{message}</p>
      <p className="text-sm mt-1 max-w-md">{description}</p>
    </div>
  );
}
