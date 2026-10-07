import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function Consent() {
  const [consentVoice, setConsentVoice] = useState(false);
  const [consentOfficial, setConsentOfficial] = useState(false);
  const [languageHint, setLanguageHint] = useState("te");
  const navigate = useNavigate();

  const handleStart = () => {
    if (!consentVoice) return;
    navigate("/live", { state: { languageHint, consentOfficial } });
  };

  return (
    <div style={{ maxWidth: 640, margin: "2rem auto", padding: "0 1rem" }}>
      <div
        style={{
          border: "1px solid #cbd5e1",
          borderRadius: "8px",
          padding: "1.5rem",
          backgroundColor: "#ffffff",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        }}
      >
        <h2 style={{ marginTop: 0, color: "#0f172a" }}>Welcome / స్వాగతం / स्वागत है</h2>
        <p style={{ color: "#334155", lineHeight: 1.6 }}>
          This assistant helps you explore suitable skill training and livelihood pathways under PM-AJAY GIA.
          You can talk freely in <strong>Telugu</strong>, <strong>Hindi</strong>, or <strong>English</strong>.
        </p>

        <div
          style={{
            backgroundColor: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "6px",
            padding: "1rem",
            marginBottom: "1.25rem",
            fontSize: "0.9rem",
            color: "#475569",
          }}
        >
          <h4 style={{ margin: "0 0 0.5rem 0", color: "#1e293b" }}>Privacy &amp; Data Notice (FR-01)</h4>
          <ul style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.5 }}>
            <li>Your audio is processed in real time by Google&apos;s Gemini speech service to enable conversation.</li>
            <li>Raw audio is <strong>never stored</strong> on our servers or databases.</li>
            <li>We <strong>do not collect or store</strong> caste, community, religion, exact address, or Aadhaar numbers.</li>
            <li>Only your skill profile and conversation transcript are processed.</li>
          </ul>
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={consentVoice}
              onChange={(e) => setConsentVoice(e.target.checked)}
              style={{ marginTop: "0.25rem" }}
            />
            <span style={{ fontSize: "0.95rem", color: "#1e293b" }}>
              <strong>Required:</strong> I agree to use voice guidance and allow real-time speech processing.
            </span>
          </label>
        </div>

        <div style={{ marginBottom: "1.25rem" }}>
          <label style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={consentOfficial}
              onChange={(e) => setConsentOfficial(e.target.checked)}
              style={{ marginTop: "0.25rem" }}
            />
            <span style={{ fontSize: "0.9rem", color: "#64748b" }}>
              Optional: Include anonymized skill interest statistics in the district official planning view.
            </span>
          </label>
        </div>

        <div style={{ marginBottom: "1.5rem" }}>
          <div style={{ fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem", color: "#334155" }}>
            Preferred Language Hint:
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {[
              { code: "te", label: "తెలుగు (Telugu)" },
              { code: "hi", label: "हिन्दी (Hindi)" },
              { code: "en", label: "English" },
            ].map((lang) => (
              <button
                key={lang.code}
                type="button"
                onClick={() => setLanguageHint(lang.code)}
                style={{
                  padding: "0.4rem 0.8rem",
                  borderRadius: "4px",
                  border: languageHint === lang.code ? "2px solid #2563eb" : "1px solid #cbd5e1",
                  backgroundColor: languageHint === lang.code ? "#eff6ff" : "#ffffff",
                  color: languageHint === lang.code ? "#1d4ed8" : "#334155",
                  fontWeight: languageHint === lang.code ? "bold" : "normal",
                  cursor: "pointer",
                }}
              >
                {lang.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleStart}
          disabled={!consentVoice}
          style={{
            width: "100%",
            padding: "0.75rem",
            fontSize: "1rem",
            fontWeight: "bold",
            borderRadius: "6px",
            border: "none",
            backgroundColor: consentVoice ? "#2563eb" : "#cbd5e1",
            color: "#ffffff",
            cursor: consentVoice ? "pointer" : "not-allowed",
          }}
        >
          Start Assistant
        </button>
      </div>
    </div>
  );
}
