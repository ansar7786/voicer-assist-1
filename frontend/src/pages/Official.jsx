export default function Official() {
  return (
    <div style={{ maxWidth: 880, margin: "2rem auto", padding: "0 1rem" }}>
      {/* Prominent Sample Data Banner (FR-64) */}
      <div
        style={{
          backgroundColor: "#fef3c7",
          border: "1px solid #f59e0b",
          color: "#92400e",
          padding: "0.75rem 1rem",
          borderRadius: "6px",
          fontWeight: "bold",
          marginBottom: "1.5rem",
          textAlign: "center",
        }}
      >
        ⚠️ Sample data (generated for demo)
      </div>

      <div
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "1.5rem",
          backgroundColor: "#ffffff",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        }}
      >
        <h2 style={{ marginTop: 0, color: "#0f172a" }}>District Skilling &amp; Livelihood Demand (Official View)</h2>
        <p style={{ color: "#64748b" }}>
          This view provides aggregated skilling demand by trade, identified skill gaps, and training seat capacity gaps.
        </p>

        <div
          style={{
            marginTop: "1.5rem",
            padding: "2rem",
            border: "2px dashed #cbd5e1",
            borderRadius: "6px",
            textAlign: "center",
            color: "#94a3b8",
          }}
        >
          <p style={{ fontSize: "1.1rem", margin: "0 0 0.5rem 0", fontWeight: "bold" }}>
            Phase 1 Shell Active
          </p>
          <p style={{ margin: 0, fontSize: "0.9rem" }}>
            Demand charts, capacity shortfall metrics, and small-cell suppression will be connected in Phase 6.
          </p>
        </div>
      </div>
    </div>
  );
}
