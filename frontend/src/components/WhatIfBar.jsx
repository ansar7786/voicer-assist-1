import React from "react";

export default function WhatIfBar({ constraints = {}, onConstraintChange, onReset }) {
  const {
    max_training_months = null,
    mobility = "",
    work_preference = "",
    time_available = "",
  } = constraints;

  const handleMonthsChange = (val) => {
    const num = val === "" || val === "all" || val === 0 ? null : parseInt(val, 10);
    onConstraintChange({
      ...constraints,
      max_training_months: num,
    });
  };

  const handleSelectChange = (field, val) => {
    onConstraintChange({
      ...constraints,
      [field]: val === "" ? null : val,
    });
  };

  const handleRemoveChip = (field) => {
    const next = { ...constraints };
    delete next[field];
    onConstraintChange(next);
  };

  const activeChips = [];
  if (max_training_months !== null && max_training_months !== undefined) {
    activeChips.push({
      key: "max_training_months",
      label: `Max Duration: ${max_training_months} ${max_training_months === 1 ? "month" : "months"}`,
    });
  }
  if (mobility) {
    activeChips.push({
      key: "mobility",
      label: `Mobility: ${mobility.replace(/_/g, " ")}`,
    });
  }
  if (work_preference) {
    activeChips.push({
      key: "work_preference",
      label: `Work: ${work_preference}`,
    });
  }
  if (time_available) {
    activeChips.push({
      key: "time_available",
      label: `Time: ${time_available.replace(/_/g, " ")}`,
    });
  }

  const hasActiveConstraints = activeChips.length > 0;

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 shadow-sm mb-6">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <span className="text-base">🎛️</span>
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wide">
            "What-If" Constraints Simulation
          </h3>
        </div>
        {hasActiveConstraints && (
          <button
            type="button"
            onClick={onReset}
            className="text-xs font-semibold text-rose-600 hover:text-rose-800 bg-rose-50 hover:bg-rose-100 px-2.5 py-1 rounded-md transition-colors border border-rose-200"
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Control row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Months Slider */}
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between items-center text-xs font-semibold text-slate-700">
            <span>Max Duration</span>
            <span className="font-mono text-indigo-600">
              {max_training_months ? `${max_training_months} mo` : "No limit"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="range"
              min="1"
              max="12"
              value={max_training_months || 12}
              onChange={(e) => handleMonthsChange(e.target.value)}
              className="w-full accent-indigo-600 cursor-pointer"
            />
          </div>
          <div className="flex justify-between text-[10px] text-slate-500">
            <span>1 mo</span>
            <button
              type="button"
              onClick={() => handleMonthsChange("all")}
              className={`underline hover:text-indigo-600 ${
                max_training_months === null ? "font-bold text-indigo-600" : ""
              }`}
            >
              No limit
            </button>
            <span>12 mo</span>
          </div>
        </div>

        {/* Mobility Dropdown */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-700">Mobility</label>
          <select
            value={mobility || ""}
            onChange={(e) => handleSelectChange("mobility", e.target.value)}
            className="w-full text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">Any distance</option>
            <option value="home_only">Home only (no travel)</option>
            <option value="local_block">Local block</option>
            <option value="within_district">Within district</option>
            <option value="nearby_districts">Nearby districts</option>
            <option value="anywhere">State / Anywhere</option>
          </select>
        </div>

        {/* Work Preference */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-700">Work Preference</label>
          <select
            value={work_preference || ""}
            onChange={(e) => handleSelectChange("work_preference", e.target.value)}
            className="w-full text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">Either (Self or Wage)</option>
            <option value="self">Self employment only</option>
            <option value="wage">Wage employment only</option>
          </select>
        </div>

        {/* Time Available */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-700">Time Available</label>
          <select
            value={time_available || ""}
            onChange={(e) => handleSelectChange("time_available", e.target.value)}
            className="w-full text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">Any time commitment</option>
            <option value="part_time">Part-time</option>
            <option value="full_time">Full-time</option>
          </select>
        </div>
      </div>

      {/* Active constraint chips */}
      {hasActiveConstraints && (
        <div className="mt-3 pt-3 border-t border-slate-200/80 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider">
            Active Constraints:
          </span>
          {activeChips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1.5 bg-indigo-50 border border-indigo-200 text-indigo-900 text-xs px-2.5 py-1 rounded-full font-medium"
            >
              <span>{chip.label}</span>
              <button
                type="button"
                onClick={() => handleRemoveChip(chip.key)}
                className="text-indigo-400 hover:text-indigo-700 font-bold ml-0.5 leading-none"
                aria-label={`Remove ${chip.label}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
