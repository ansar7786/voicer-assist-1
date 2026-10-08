import React from "react";

export default function PathwayCard({ pathway, onSelectWhy }) {
  if (!pathway) return null;

  const {
    id = "pathway",
    name = "Livelihood Pathway",
    trade = "general",
    nsqf_level = 1,
    duration_months = 3,
    route = "either",
    delivery_mode = "either",
    nearest_centre = null,
    training_centres = [],
    factors = [],
  } = pathway;

  const routeLabel =
    route === "self" ? "Self Employment" : route === "wage" ? "Wage Employment" : "Self / Wage";

  const deliveryLabel =
    delivery_mode === "home_based"
      ? "Home Based"
      : delivery_mode === "centre_based"
      ? "Centre Based"
      : "Home / Centre";

  // Handle both pathway.opportunity_status and pathway.opportunity object
  const oppStatus =
    pathway.opportunity_status ||
    pathway.opportunity?.status ||
    "No verified opportunity found";

  const isOppVerified = String(oppStatus).startsWith("Verified:");
  const isNoOpp = oppStatus === "No verified opportunity found";
  const isOppSample = Boolean(
    pathway.opportunity?.is_sample ||
    (typeof oppStatus === "string" && oppStatus.toLowerCase().includes("sample"))
  );

  // Handle both nearest_centre and training_centres
  const centre = nearest_centre || (Array.isArray(training_centres) && training_centres[0]) || null;
  const isCentreSample = Boolean(centre?.is_sample || centre?.sample);

  return (
    <div
      data-testid={`pathway-card-${id}`}
      className="p-5 bg-white border border-slate-200 rounded-xl shadow-sm hover:shadow-md transition-shadow duration-200 flex flex-col justify-between"
    >
      <div>
        {/* Header: Trade and NSQF badge */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
              {trade}
            </span>
            <h3 className="text-lg font-bold text-slate-800 mt-1 leading-snug">{name}</h3>
          </div>
          <span className="shrink-0 text-xs font-medium bg-slate-100 text-slate-700 px-2.5 py-1 rounded-md border border-slate-200">
            NSQF L{nsqf_level}
          </span>
        </div>

        {/* Key Metrics / Tags */}
        <div className="flex flex-wrap gap-2 text-xs text-slate-600 my-3">
          <span className="bg-slate-100 px-2.5 py-1 rounded-md flex items-center gap-1 font-medium">
            ⏱️ {duration_months} {duration_months === 1 ? "month" : "months"}
          </span>
          <span className="bg-slate-100 px-2.5 py-1 rounded-md flex items-center gap-1 font-medium">
            💼 {routeLabel}
          </span>
          <span className="bg-slate-100 px-2.5 py-1 rounded-md flex items-center gap-1 font-medium">
            📍 {deliveryLabel}
          </span>
        </div>

        {/* Training Centre info */}
        <div className="text-xs text-slate-600 mb-2.5 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
          <div className="font-semibold text-slate-700 flex items-center justify-between mb-1">
            <span>Training Centre</span>
            {isCentreSample && (
              <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-mono">
                Sample Centre
              </span>
            )}
          </div>
          {centre ? (
            <div className="text-slate-600">
              <span className="font-medium text-slate-800">{centre.name}</span>
              {centre.block && (
                <span className="text-slate-500"> ({centre.block})</span>
              )}
              {centre.seats && (
                <span className="text-slate-500"> • {centre.seats} seats</span>
              )}
            </div>
          ) : (
            <span className="text-slate-500 italic">No affiliated local centre in immediate block</span>
          )}
        </div>

        {/* Opportunity status honesty tag */}
        <div className="text-xs mb-3">
          <div className="font-semibold text-slate-700 flex items-center justify-between mb-1">
            <span>Market Opportunity</span>
            {isOppSample && (
              <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-mono">
                Sample Opportunity
              </span>
            )}
          </div>
          {isNoOpp ? (
            <div className="p-2 bg-amber-50 border border-amber-200 text-amber-900 rounded-md font-medium text-xs flex items-center gap-1.5">
              <span>⚠️</span>
              <span>No verified opportunity found</span>
            </div>
          ) : (
            <div
              className={`p-2 rounded-md text-xs font-medium border ${
                isOppVerified
                  ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                  : "bg-blue-50 border-blue-200 text-blue-900"
              }`}
            >
              {oppStatus}
            </div>
          )}
        </div>

        {/* High-match factor badges preview */}
        {Array.isArray(factors) && factors.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {factors
              .filter((f) => f && (f.label === "High" || f.label === "Medium"))
              .slice(0, 3)
              .map((f, idx) => {
                const rawName = f.factor || f.name || "Factor";
                const factorDisplay = String(rawName).replace(/_/g, " ");
                return (
                  <span
                    key={idx}
                    className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                      f.label === "High"
                        ? "bg-green-100 text-green-800"
                        : "bg-blue-100 text-blue-800"
                    }`}
                    title={f.reason || ""}
                  >
                    ✓ {factorDisplay}
                  </span>
                );
              })}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
        <button
          type="button"
          onClick={() => onSelectWhy && onSelectWhy(pathway)}
          className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline flex items-center gap-1 py-1"
        >
          <span>💡 Why this pathway?</span>
        </button>
      </div>
    </div>
  );
}
