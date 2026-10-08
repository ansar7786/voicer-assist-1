import React, { useState } from "react";

export default function DiffBanner({ diff, excluded = [] }) {
  const [showExcluded, setShowExcluded] = useState(false);

  if (!diff && (!excluded || excluded.length === 0)) {
    return null;
  }

  const added = diff?.added || [];
  const removed = diff?.removed || [];
  const kept = diff?.kept || [];

  const hasDiffItems = added.length > 0 || removed.length > 0 || kept.length > 0;
  if (!hasDiffItems && (!excluded || excluded.length === 0)) {
    return null;
  }

  return (
    <div
      data-testid="diff-banner"
      className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base">🔄</span>
          <h4 className="text-sm font-bold text-slate-800 uppercase tracking-wide">
            Pathway Changes (Diff Summary)
          </h4>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {added.length > 0 && (
            <span className="bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full font-semibold">
              +{added.length} added
            </span>
          )}
          {removed.length > 0 && (
            <span className="bg-rose-50 text-rose-800 border border-rose-200 px-2 py-0.5 rounded-full font-semibold">
              -{removed.length} dropped
            </span>
          )}
          {kept.length > 0 && (
            <span className="bg-slate-100 text-slate-700 border border-slate-200 px-2 py-0.5 rounded-full font-medium">
              {kept.length} kept
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Dropped / Removed */}
        {removed.length > 0 && (
          <div className="p-3 bg-rose-50/60 border border-rose-200 rounded-lg">
            <div className="text-xs font-bold text-rose-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <span>🔻 Dropped Pathways ({removed.length})</span>
            </div>
            <ul className="space-y-1.5">
              {removed.map((item, idx) => (
                <li key={idx} className="text-xs text-rose-900">
                  <span className="font-semibold">{item.name || item.trade}</span>
                  {item.reason && (
                    <span className="text-rose-700 block text-[11px] mt-0.5 pl-2 border-l-2 border-rose-300">
                      Reason: {item.reason}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Added */}
        {added.length > 0 && (
          <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg">
            <div className="text-xs font-bold text-emerald-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <span>✨ Newly Added Pathways ({added.length})</span>
            </div>
            <ul className="space-y-1.5">
              {added.map((item, idx) => (
                <li key={idx} className="text-xs text-emerald-900">
                  <span className="font-semibold">{item.name || item.trade}</span>
                  {item.reason && (
                    <span className="text-emerald-700 block text-[11px] mt-0.5 pl-2 border-l-2 border-emerald-300">
                      Reason: {item.reason}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Kept summary if nothing was added or removed */}
      {removed.length === 0 && added.length === 0 && kept.length > 0 && (
        <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600">
          <span>All previous pathways remained qualified under current filters.</span>
        </div>
      )}

      {/* Collapsible Excluded list */}
      {excluded && excluded.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <button
            type="button"
            onClick={() => setShowExcluded(!showExcluded)}
            className="text-xs font-semibold text-slate-600 hover:text-slate-800 flex items-center gap-1.5"
          >
            <span>{showExcluded ? "▼" : "▶"}</span>
            <span>View Excluded Opportunities ({excluded.length})</span>
          </button>

          {showExcluded && (
            <div className="mt-2.5 p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <p className="text-[11px] text-slate-500 mb-2 font-medium">
                The following pathways were evaluated but did not meet profile requirements or constraints:
              </p>
              <ul className="space-y-2">
                {excluded.map((item, idx) => (
                  <li key={idx} className="text-xs text-slate-700 border-b border-slate-200 pb-1.5 last:border-0 last:pb-0">
                    <span className="font-semibold text-slate-900">{item.name || item.trade}</span>
                    <span className="text-slate-600 block text-[11px] pl-2 border-l-2 border-slate-300 mt-0.5">
                      Excluded because: {item.reason}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
