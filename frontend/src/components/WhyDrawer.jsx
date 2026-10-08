import React, { useState } from "react";

export default function WhyDrawer({ pathway, profile, onClose }) {
  if (!pathway) return null;

  const [explanation, setExplanation] = useState(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [explanationError, setExplanationError] = useState(null);

  const { name, factors = [], trade, duration_months, route, delivery_mode } = pathway;

  const handleExplain = async () => {
    setLoadingExplanation(true);
    setExplanationError(null);
    try {
      const res = await fetch("/api/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pathway_name: name,
          factors: factors.map((f) => ({
            name: f.name,
            label: f.label,
            reason: f.reason,
          })),
          user_profile: profile || {},
          language: profile?.language || "english",
        }),
      });

      if (!res.ok) {
        throw new Error(`Failed to explain (${res.status})`);
      }

      const data = await res.json();
      setExplanation(data.explanation || "No explanation returned.");
    } catch (err) {
      console.error("Explain error:", err);
      setExplanationError("Could not generate AI explanation. Showing factor reasons below.");
    } finally {
      setLoadingExplanation(false);
    }
  };

  const getBadgeStyle = (label) => {
    switch (label) {
      case "High":
        return "bg-emerald-100 text-emerald-800 border-emerald-300";
      case "Medium":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "Low":
        return "bg-amber-100 text-amber-800 border-amber-300";
      default:
        return "bg-slate-100 text-slate-700 border-slate-300";
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="why-drawer-title"
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-sm transition-opacity"
    >
      <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col justify-between overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between border-b pb-4 mb-4">
            <div>
              <span className="text-xs font-semibold uppercase text-indigo-600 tracking-wider">
                Pathway Assessment
              </span>
              <h2 id="why-drawer-title" className="text-xl font-bold text-slate-900 mt-1">
                {name}
              </h2>
              <div className="text-xs text-slate-500 mt-1">
                {trade} • {duration_months} mo • {route}
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              aria-label="Close drawer"
            >
              ✕
            </button>
          </div>

          {/* AI Plain Language Explanation */}
          <div className="mb-6 p-4 rounded-xl bg-indigo-50/70 border border-indigo-100">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-indigo-900 uppercase tracking-wider flex items-center gap-1.5">
                <span>✨</span> Plain Language Summary
              </span>
              <button
                type="button"
                onClick={handleExplain}
                disabled={loadingExplanation}
                className="text-xs bg-indigo-600 text-white font-medium px-3 py-1.5 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm"
              >
                {loadingExplanation ? "Explaining..." : explanation ? "Regenerate" : "Explain"}
              </button>
            </div>

            {explanation ? (
              <p className="text-sm text-slate-800 leading-relaxed mt-2 whitespace-pre-wrap">
                {explanation}
              </p>
            ) : (
              <p className="text-xs text-slate-600 mt-1">
                Click "Explain" to get an AI summary connecting this pathway directly to your background and preferences.
              </p>
            )}

            {explanationError && (
              <p className="text-xs text-red-600 mt-2">{explanationError}</p>
            )}
          </div>

          {/* Contributing Factor Breakdown */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
              Matching Factors (Deterministic Assessment)
            </h3>

            {factors.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No specific factor details recorded.</p>
            ) : (
              factors.map((factor, index) => {
                const fname = factor.name || factor.factor || `Factor ${index + 1}`;
                return (
                  <div
                    key={index}
                    className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/50 flex flex-col gap-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm text-slate-800 capitalize">
                        {String(fname).replace(/_/g, " ")}
                      </span>
                      <span
                        className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${getBadgeStyle(
                          factor.label
                        )}`}
                      >
                        {factor.label} Match
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 leading-normal">{factor.reason}</p>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-slate-50 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-200 text-slate-700 text-xs font-medium rounded-lg hover:bg-slate-300 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
