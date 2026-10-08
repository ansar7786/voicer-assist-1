import React, { useState } from "react";
import PathwayCard from "../components/PathwayCard";
import WhyDrawer from "../components/WhyDrawer";

const EDUCATION_OPTIONS = [
  { value: "none", label: "No formal schooling" },
  { value: "primary", label: "Primary (up to 5th)" },
  { value: "8th", label: "8th Pass" },
  { value: "10th", label: "10th Pass (SSC)" },
  { value: "12th", label: "12th / Intermediate" },
  { value: "graduate", label: "Graduate & above" },
];

const TRADE_OPTIONS = [
  { value: "tailoring", label: "Tailoring & Apparel" },
  { value: "catering", label: "Catering & Hospitality" },
  { value: "solar_technician", label: "Solar PV Technician" },
  { value: "electrician", label: "Electrician / Electricals" },
  { value: "beauty_wellness", label: "Beauty & Wellness" },
  { value: "dairy_farming", label: "Dairy & Livestock Farming" },
  { value: "retail_sales", label: "Retail Sales Associate" },
];

const MOBILITY_OPTIONS = [
  { value: "home_only", label: "Home only (no travel)" },
  { value: "local_block", label: "Within local block" },
  { value: "within_district", label: "Within district" },
  { value: "nearby_districts", label: "Nearby districts" },
  { value: "anywhere", label: "State / Anywhere" },
];

export default function ManualForm() {
  const [formData, setFormData] = useState({
    education_level: "10th",
    interests: ["tailoring"],
    skills: "hand_sewing",
    assets: "sewing machine",
    mobility: "home_only",
    max_training_months: 3,
    work_preference: "self",
    time_available: "part_time",
    location_block: "Anandapuram",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pathways, setPathways] = useState([]);
  const [excluded, setExcluded] = useState([]);
  const [selectedWhyPathway, setSelectedWhyPathway] = useState(null);

  const handleChange = (field, val) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
  };

  const handleInterestToggle = (trade) => {
    setFormData((prev) => {
      const current = prev.interests || [];
      const updated = current.includes(trade)
        ? current.filter((t) => t !== trade)
        : [...current, trade];
      return { ...prev, interests: updated.length ? updated : [trade] };
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const skillsList = formData.skills
      ? formData.skills.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean)
      : [];

    const assetsList = formData.assets
      ? formData.assets.split(",").map((a) => a.trim().toLowerCase()).filter(Boolean)
      : [];

    const profilePayload = {
      education_level: formData.education_level,
      interests: formData.interests,
      skills: skillsList,
      assets: assetsList,
      mobility: formData.mobility,
      max_training_months: Number(formData.max_training_months) || 6,
      work_preference: formData.work_preference,
      time_available: formData.time_available,
      location_block: formData.location_block,
    };

    try {
      const res = await fetch("/api/pathways", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: profilePayload }),
      });

      if (!res.ok) {
        throw new Error(`Engine returned error (${res.status})`);
      }

      const data = await res.json();
      setPathways(data.pathways || []);
      setExcluded(data.excluded || []);
    } catch (err) {
      console.error("Manual pathway search error:", err);
      setError(err.message || "Failed to compute pathways");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 960, margin: "2rem auto", padding: "0 1rem", fontFamily: "var(--sans, sans-serif)" }}>
      {/* Facilitator Notice */}
      <div
        style={{
          padding: "0.85rem 1.25rem",
          backgroundColor: "#eff6ff",
          border: "1px solid #bfdbfe",
          color: "#1e40af",
          borderRadius: "8px",
          marginBottom: "1.5rem",
          fontSize: "0.88rem",
          display: "flex",
          alignItems: "center",
          gap: "0.6rem",
        }}
      >
        <span>📋</span>
        <span>
          <strong>Facilitator &amp; Manual Entry Path (Phase 7):</strong> Direct deterministic intake for field facilitators without live voice capture.
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.5rem" }}>
        {/* Form Panel */}
        <form
          onSubmit={handleSubmit}
          style={{
            backgroundColor: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "12px",
            padding: "1.75rem",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <h2 style={{ fontSize: "1.25rem", fontWeight: "bold", color: "#0f172a", margin: "0 0 1.25rem 0" }}>
            Candidate Profile Intake
          </h2>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1.25rem" }}>
            {/* Education Level */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.4rem" }}>
                Highest Education Completed
              </label>
              <select
                value={formData.education_level}
                onChange={(e) => handleChange("education_level", e.target.value)}
                style={{
                  width: "100%", padding: "0.6rem", borderRadius: "6px",
                  border: "1px solid #cbd5e1", fontSize: "0.9rem", backgroundColor: "#f8fafc",
                }}
              >
                {EDUCATION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* Mobility */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.4rem" }}>
                Mobility &amp; Travel Flexibility
              </label>
              <select
                value={formData.mobility}
                onChange={(e) => handleChange("mobility", e.target.value)}
                style={{
                  width: "100%", padding: "0.6rem", borderRadius: "6px",
                  border: "1px solid #cbd5e1", fontSize: "0.9rem", backgroundColor: "#f8fafc",
                }}
              >
                {MOBILITY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* Work Preference */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.4rem" }}>
                Work Style Preference
              </label>
              <select
                value={formData.work_preference}
                onChange={(e) => handleChange("work_preference", e.target.value)}
                style={{
                  width: "100%", padding: "0.6rem", borderRadius: "6px",
                  border: "1px solid #cbd5e1", fontSize: "0.9rem", backgroundColor: "#f8fafc",
                }}
              >
                <option value="self">Self Employment / Own Business</option>
                <option value="wage">Wage Employment / Salaried Job</option>
                <option value="either">Either (Open to both)</option>
              </select>
            </div>

            {/* Max Training Months */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#334155" }}>
                  Max Training Duration
                </label>
                <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#2563eb" }}>
                  {formData.max_training_months} months
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="12"
                value={formData.max_training_months}
                onChange={(e) => handleChange("max_training_months", e.target.value)}
                style={{ width: "100%", accentColor: "#2563eb" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#64748b" }}>
                <span>1 mo</span>
                <span>6 mo</span>
                <span>12 mo</span>
              </div>
            </div>
          </div>

          {/* Interests */}
          <div style={{ marginTop: "1.25rem" }}>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.4rem" }}>
              Trades of Interest (Select one or more)
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
              {TRADE_OPTIONS.map((t) => {
                const isSelected = formData.interests.includes(t.value);
                return (
                  <button
                    type="button"
                    key={t.value}
                    onClick={() => handleInterestToggle(t.value)}
                    style={{
                      padding: "0.45rem 0.8rem",
                      borderRadius: "9999px",
                      fontSize: "0.82rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      border: isSelected ? "1px solid #2563eb" : "1px solid #cbd5e1",
                      backgroundColor: isSelected ? "#eff6ff" : "#ffffff",
                      color: isSelected ? "#1e40af" : "#475569",
                    }}
                  >
                    {isSelected ? "✓ " : ""}{t.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Skills & Assets Text Inputs */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "1.25rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.4rem" }}>
                Existing Skills (comma-separated)
              </label>
              <input
                type="text"
                value={formData.skills}
                onChange={(e) => handleChange("skills", e.target.value)}
                placeholder="e.g. cutting, hand_sewing, cooking"
                style={{
                  width: "100%", padding: "0.55rem 0.8rem", borderRadius: "6px",
                  border: "1px solid #cbd5e1", fontSize: "0.88rem",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.4rem" }}>
                Owned Tools / Assets (comma-separated)
              </label>
              <input
                type="text"
                value={formData.assets}
                onChange={(e) => handleChange("assets", e.target.value)}
                placeholder="e.g. sewing machine, kitchen tools"
                style={{
                  width: "100%", padding: "0.55rem 0.8rem", borderRadius: "6px",
                  border: "1px solid #cbd5e1", fontSize: "0.88rem",
                }}
              />
            </div>
          </div>

          {/* Submit Button */}
          <div style={{ marginTop: "1.5rem", display: "flex", justifyContent: "flex-end" }}>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: "0.7rem 1.8rem",
                backgroundColor: "#2563eb",
                color: "#ffffff",
                fontWeight: "bold",
                fontSize: "0.95rem",
                borderRadius: "8px",
                border: "none",
                cursor: loading ? "not-allowed" : "pointer",
                boxShadow: "0 2px 4px rgba(37,99,235,0.25)",
              }}
            >
              {loading ? "Evaluating Engine…" : "🔍 Find Recommended Pathways"}
            </button>
          </div>
        </form>

        {error && (
          <div style={{ padding: "1rem", backgroundColor: "#fee2e2", color: "#991b1b", borderRadius: "8px" }}>
            {error}
          </div>
        )}

        {/* Results Section */}
        {pathways.length > 0 && (
          <div style={{ marginTop: "1rem" }}>
            <h3 style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#0f172a", marginBottom: "1rem" }}>
              Matched Livelihood Pathways ({pathways.length})
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1rem" }}>
              {pathways.map((pw) => (
                <PathwayCard
                  key={pw.id}
                  pathway={pw}
                  onSelectWhy={(p) => setSelectedWhyPathway(p)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Excluded Section */}
        {excluded.length > 0 && (
          <div style={{ padding: "1rem", backgroundColor: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
            <h4 style={{ fontSize: "0.9rem", fontWeight: "bold", color: "#475569", margin: "0 0 0.5rem 0" }}>
              Excluded Qualifications ({excluded.length})
            </h4>
            <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: "0.82rem", color: "#64748b" }}>
              {excluded.map((ex, idx) => (
                <li key={idx} style={{ margin: "0.2rem 0" }}>
                  <strong>{ex.name}</strong>: {ex.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* WhyDrawer */}
      {selectedWhyPathway && (
        <WhyDrawer
          pathway={selectedWhyPathway}
          profile={formData}
          onClose={() => setSelectedWhyPathway(null)}
        />
      )}
    </div>
  );
}
