/**
 * ProfileCard — Phase 4
 *
 * Displays profile fields as colour-coded chips:
 *   • Green  (stated)   — person explicitly stated the fact
 *   • Amber  (inferred) — assistant inferred from context
 *   • Grey   (missing)  — high-priority field not yet captured
 *
 * High-priority fields that must be highlighted when missing:
 *   education_level, mobility, max_training_months, work_preference, interests
 *
 * Props:
 *   profile    : {field: value, ...}
 *   confidence : {field: "stated"|"inferred", ...}
 *   confirmed  : bool
 *   sessionId  : string   (for PATCH requests)
 *   onPatch    : (field, value) => void   (callback after successful PATCH)
 */
import { useState } from "react";

const HIGH_PRIORITY = [
  "education_level",
  "mobility",
  "max_training_months",
  "work_preference",
  "interests",
];

const FIELD_LABELS = {
  education_level: "Education",
  mobility: "Can Travel",
  max_training_months: "Training limit",
  work_preference: "Work type",
  interests: "Interests",
  skills: "Skills",
  current_or_past_work: "Past work",
  time_available: "Availability",
  urgency_of_income: "Income urgency",
  location_block: "Block / Mandal",
  language: "Language",
  assets: "Assets",
};

const CHIP_STYLE_BASE = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.3rem",
  padding: "0.25rem 0.65rem",
  borderRadius: "9999px",
  fontSize: "0.8rem",
  fontWeight: 500,
  lineHeight: 1.4,
  cursor: "default",
  margin: "0.2rem",
};

const CHIP_COLORS = {
  stated:   { bg: "#dcfce7", border: "#86efac", text: "#166534" },  // Green
  inferred: { bg: "#fef9c3", border: "#fde047", text: "#854d0e" },  // Amber
  missing:  { bg: "#f1f5f9", border: "#cbd5e1", text: "#94a3b8" },  // Grey
};

function chipStyle(kind) {
  const c = CHIP_COLORS[kind] || CHIP_COLORS.missing;
  return {
    ...CHIP_STYLE_BASE,
    backgroundColor: c.bg,
    border: `1px solid ${c.border}`,
    color: c.text,
  };
}

function formatValue(field, value) {
  if (Array.isArray(value)) return value.join(", ") || "—";
  if (value === null || value === undefined) return "—";
  if (field === "max_training_months") return `${value} month${value === 1 ? "" : "s"}`;
  return String(value);
}

// Inline edit form for a single field
function EditForm({ field, currentValue, sessionId, onSave, onCancel }) {
  const [val, setVal] = useState(
    Array.isArray(currentValue) ? currentValue.join(", ") : (currentValue ?? "")
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    if (!sessionId) { onCancel(); return; }
    setSaving(true);
    setError("");
    try {
      const parsed = val.includes(",")
        ? val.split(",").map((s) => s.trim()).filter(Boolean)
        : val.trim();
      const res = await fetch(`/api/session/${sessionId}/profile`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field, value: parsed, actor: "manual" }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      onSave(field, data.new_value);
    } catch (e) {
      setError(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", gap: "0.3rem", alignItems: "center", flexWrap: "wrap" }}>
      <input
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") onCancel(); }}
        style={{
          padding: "0.25rem 0.5rem",
          fontSize: "0.85rem",
          borderRadius: "4px",
          border: "1px solid #94a3b8",
          minWidth: 120,
        }}
        autoFocus
      />
      <button
        onClick={save}
        disabled={saving}
        style={{
          padding: "0.25rem 0.5rem",
          fontSize: "0.8rem",
          borderRadius: "4px",
          border: "none",
          backgroundColor: "#2563eb",
          color: "#fff",
          cursor: saving ? "not-allowed" : "pointer",
        }}
      >
        {saving ? "…" : "Save"}
      </button>
      <button
        onClick={onCancel}
        style={{
          padding: "0.25rem 0.5rem",
          fontSize: "0.8rem",
          borderRadius: "4px",
          border: "1px solid #cbd5e1",
          backgroundColor: "transparent",
          cursor: "pointer",
        }}
      >
        Cancel
      </button>
      {error && <span style={{ color: "#dc2626", fontSize: "0.75rem" }}>{error}</span>}
    </div>
  );
}

export default function ProfileCard({ profile = {}, confidence = {}, confirmed = false, sessionId, onPatch }) {
  const [editingField, setEditingField] = useState(null);

  // All known fields + any extra fields the model populated
  const allFields = Array.from(
    new Set([...Object.keys(FIELD_LABELS), ...Object.keys(profile)])
  ).filter((f) => !f.startsWith("_"));

  const handleSave = (field, newValue) => {
    setEditingField(null);
    if (onPatch) onPatch(field, newValue);
  };

  const isEmpty = Object.keys(profile).filter((k) => !k.startsWith("_")).length === 0;

  return (
    <div
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: "10px",
        padding: "1.25rem",
        marginBottom: "1.5rem",
        backgroundColor: "#ffffff",
        boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.75rem",
        }}
      >
        <h3 style={{ margin: 0, fontSize: "1rem", color: "#0f172a" }}>
          📋 Profile Card
        </h3>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          {confirmed && (
            <span
              style={{
                ...chipStyle("stated"),
                fontWeight: 700,
                fontSize: "0.75rem",
              }}
            >
              ✓ Confirmed
            </span>
          )}
          {/* Legend */}
          <span style={chipStyle("stated")}>● Stated</span>
          <span style={chipStyle("inferred")}>● Inferred</span>
          <span style={chipStyle("missing")}>● Missing</span>
        </div>
      </div>

      {isEmpty ? (
        <p
          style={{
            color: "#94a3b8",
            fontStyle: "italic",
            fontSize: "0.9rem",
            margin: 0,
          }}
        >
          Profile fields will appear here as you speak. High-priority fields are highlighted.
        </p>
      ) : null}

      {/* Fields */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {allFields.map((field) => {
          const value = profile[field];
          const conf = confidence[field];
          const hasValue = value !== undefined && value !== null &&
            !(Array.isArray(value) && value.length === 0);
          const isPriority = HIGH_PRIORITY.includes(field);
          const chipKind = hasValue ? (conf || "stated") : "missing";

          // Skip non-priority missing fields to keep card clean
          if (!hasValue && !isPriority) return null;

          const label = FIELD_LABELS[field] || field;

          return (
            <div
              key={field}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                flexWrap: "wrap",
                padding: "0.3rem 0",
                borderBottom: "1px solid #f1f5f9",
              }}
            >
              <span
                style={{
                  width: 120,
                  fontSize: "0.8rem",
                  color: "#64748b",
                  fontWeight: isPriority ? 600 : 400,
                  flexShrink: 0,
                }}
              >
                {isPriority && !hasValue ? `⚡ ${label}` : label}
              </span>

              {editingField === field ? (
                <EditForm
                  field={field}
                  currentValue={value}
                  sessionId={sessionId}
                  onSave={handleSave}
                  onCancel={() => setEditingField(null)}
                />
              ) : (
                <>
                  <span style={chipStyle(chipKind)}>
                    {hasValue ? formatValue(field, value) : "Not yet captured"}
                  </span>
                  {/* Edit button — only for fields with a value */}
                  {hasValue && sessionId && (
                    <button
                      onClick={() => setEditingField(field)}
                      title={`Edit ${label}`}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        fontSize: "0.8rem",
                        color: "#94a3b8",
                        padding: "0 0.2rem",
                      }}
                    >
                      ✏️
                    </button>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Unconfirmed preview warning */}
      {!confirmed && !isEmpty && (
        <p
          style={{
            marginTop: "0.75rem",
            fontSize: "0.78rem",
            color: "#92400e",
            backgroundColor: "#fef3c7",
            border: "1px solid #fde68a",
            borderRadius: "4px",
            padding: "0.4rem 0.6rem",
          }}
        >
          ⚠️ Profile not yet confirmed — pathway results would be an unconfirmed preview.
        </p>
      )}
    </div>
  );
}
