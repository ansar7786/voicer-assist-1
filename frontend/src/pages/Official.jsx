import React, { useState, useEffect } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";

export default function Official() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedBlock, setSelectedBlock] = useState("");
  const [selectedTrade, setSelectedTrade] = useState("");

  const fetchData = async (block = "", trade = "") => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (block) params.set("block", block);
      if (trade) params.set("trade", trade);

      const res = await fetch(`/api/official/summary?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`Failed to load official summary (${res.status})`);
      }
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error("Error fetching official summary:", err);
      setError(err.message || "Failed to load district data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(selectedBlock, selectedTrade);
  }, [selectedBlock, selectedTrade]);

  const handleResetFilters = () => {
    setSelectedBlock("");
    setSelectedTrade("");
  };

  const sampleData = data?.sample_data || {};
  const demandByTrade = sampleData.demand_by_trade || [];
  const skillGaps = sampleData.skill_gaps || [];
  const capacity = sampleData.capacity || [];
  const consented = data?.consented_sessions || { total_consented: 0, sessions: [] };

  const shortfallsCount = capacity.filter((c) => c.is_shortfall).length;

  return (
    <div style={{ maxWidth: 1100, margin: "2rem auto", padding: "0 1rem", fontFamily: "var(--sans, sans-serif)" }}>
      {/* ── 1. Prominent Sample Data Banner (FR-64) ── */}
      <div
        id="official-sample-banner"
        style={{
          backgroundColor: "#fef3c7",
          border: "2px solid #f59e0b",
          color: "#92400e",
          padding: "0.85rem 1.25rem",
          borderRadius: "8px",
          fontWeight: "bold",
          marginBottom: "1.5rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <span style={{ fontSize: "1.25rem" }}>⚠️</span>
          <span>Sample data (generated for demo) — All district demand counts and seat capacities are seeded representations.</span>
        </div>
        <span style={{ fontSize: "0.75rem", backgroundColor: "#fde68a", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>
          PRD FR-64
        </span>
      </div>

      {/* Header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: "bold", color: "#0f172a", margin: "0 0 0.4rem 0" }}>
          District Skilling &amp; Livelihood Demand (Official View)
        </h1>
        <p style={{ margin: 0, color: "#64748b", fontSize: "0.95rem" }}>
          Aggregated livelihood interest patterns, critical skill deficiencies, and institutional training seat shortfalls.
        </p>
      </div>

      {/* ── 2. Filter Bar ── */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "1rem",
          padding: "1rem 1.25rem",
          backgroundColor: "#ffffff",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
          marginBottom: "1.5rem",
          boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#334155" }}>Filter Block:</label>
          <select
            id="select-filter-block"
            value={selectedBlock}
            onChange={(e) => setSelectedBlock(e.target.value)}
            style={{
              padding: "0.45rem 0.8rem",
              borderRadius: "6px",
              border: "1px solid #cbd5e1",
              fontSize: "0.85rem",
              backgroundColor: "#f8fafc",
              color: "#1e293b",
            }}
          >
            <option value="">All Blocks</option>
            {data?.available_blocks?.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#334155" }}>Filter Trade:</label>
          <select
            id="select-filter-trade"
            value={selectedTrade}
            onChange={(e) => setSelectedTrade(e.target.value)}
            style={{
              padding: "0.45rem 0.8rem",
              borderRadius: "6px",
              border: "1px solid #cbd5e1",
              fontSize: "0.85rem",
              backgroundColor: "#f8fafc",
              color: "#1e293b",
            }}
          >
            <option value="">All Trades</option>
            {data?.available_trades?.map((t) => (
              <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
            ))}
          </select>
        </div>

        {(selectedBlock || selectedTrade) && (
          <button
            type="button"
            onClick={handleResetFilters}
            style={{
              padding: "0.45rem 0.9rem",
              fontSize: "0.8rem",
              fontWeight: 600,
              backgroundColor: "#fee2e2",
              color: "#991b1b",
              border: "1px solid #fecaca",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            Clear Filters
          </button>
        )}

        <div style={{ marginLeft: "auto", fontSize: "0.8rem", color: "#64748b" }}>
          Small-cell rule: <em>counts &lt; 5 merged into "Other (suppressed)"</em>
        </div>
      </div>

      {loading && (
        <div style={{ padding: "3rem", textAlign: "center", color: "#64748b" }}>
          Loading district aggregations from database…
        </div>
      )}

      {error && (
        <div style={{ padding: "1rem", backgroundColor: "#fee2e2", color: "#991b1b", borderRadius: "8px", marginBottom: "1rem" }}>
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          {/* ── 3. High-level metric KPI cards ── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ padding: "1.2rem", backgroundColor: "#ffffff", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>
                Total Interested Candidates
              </div>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#1e293b", marginTop: "0.25rem" }}>
                {sampleData.total_profiles || 0}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.25rem" }}>
                Synthetic sample dataset
              </div>
            </div>

            <div style={{ padding: "1.2rem", backgroundColor: "#ffffff", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>
                Leading Demand Trade
              </div>
              <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "#2563eb", marginTop: "0.4rem", textTransform: "capitalize" }}>
                {demandByTrade[0]?.trade?.replace(/_/g, " ") || "None"}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.25rem" }}>
                {demandByTrade[0]?.count || 0} interested profiles
              </div>
            </div>

            <div style={{ padding: "1.2rem", backgroundColor: "#ffffff", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>
                Capacity Shortfalls
              </div>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: shortfallsCount > 0 ? "#dc2626" : "#16a34a", marginTop: "0.25rem" }}>
                {shortfallsCount} {shortfallsCount === 1 ? "trade" : "trades"}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.25rem" }}>
                Demand exceeds available seats
              </div>
            </div>

            <div style={{ padding: "1.2rem", backgroundColor: "#ffffff", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>
                Consented Real Sessions
              </div>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#059669", marginTop: "0.25rem" }}>
                {consented.total_consented || 0}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.25rem" }}>
                Live user sessions opted-in
              </div>
            </div>
          </div>

          {/* ── 4. Main Charts & Gaps Row ── */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "1.5rem", marginBottom: "1.5rem" }}>
            {/* Recharts Bar Chart: Demand by Trade */}
            <div style={{ backgroundColor: "#ffffff", borderRadius: "10px", border: "1px solid #e2e8f0", padding: "1.25rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ fontSize: "1rem", fontWeight: "bold", color: "#0f172a", margin: 0 }}>
                  Livelihood Demand by Trade
                </h3>
                <span style={{ fontSize: "0.75rem", color: "#64748b" }}>Count of interested profiles</span>
              </div>

              {demandByTrade.length === 0 ? (
                <div style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>No demand records found.</div>
              ) : (
                <div style={{ width: "100%", height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={demandByTrade.map((d) => ({
                        name: d.trade.replace(/_/g, " "),
                        count: d.count,
                        is_suppressed: d.is_suppressed,
                      }))}
                      margin={{ top: 10, right: 20, left: -10, bottom: 40 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis
                        dataKey="name"
                        angle={-25}
                        textAnchor="end"
                        tick={{ fontSize: 11, fill: "#475569" }}
                        interval={0}
                      />
                      <YAxis tick={{ fontSize: 11, fill: "#475569" }} allowDecimals={false} />
                      <Tooltip
                        formatter={(val, name, item) => [
                          `${val} profiles`,
                          item.payload.is_suppressed ? "Merged (< 5)" : "Interested",
                        ]}
                      />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {demandByTrade.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={entry.is_suppressed ? "#94a3b8" : "#2563eb"}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Top Skill Gaps List */}
            <div style={{ backgroundColor: "#ffffff", borderRadius: "10px", border: "1px solid #e2e8f0", padding: "1.25rem", display: "flex", flexDirection: "column" }}>
              <div style={{ marginBottom: "0.75rem" }}>
                <h3 style={{ fontSize: "1rem", fontWeight: "bold", color: "#0f172a", margin: 0 }}>
                  Top Identified Skill Gaps
                </h3>
                <p style={{ fontSize: "0.75rem", color: "#64748b", margin: "0.2rem 0 0 0" }}>
                  Deficiencies reported by candidates seeking entry
                </p>
              </div>

              {skillGaps.length === 0 ? (
                <div style={{ color: "#94a3b8", fontSize: "0.85rem", margin: "auto" }}>No skill gaps recorded.</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", overflowY: "auto", flex: 1 }}>
                  {skillGaps.map((sg, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: "0.6rem 0.8rem",
                        backgroundColor: "#f8fafc",
                        borderRadius: "6px",
                        border: "1px solid #e2e8f0",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#334155" }}>
                        {sg.skill}
                      </span>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          backgroundColor: "#fee2e2",
                          color: "#991b1b",
                          padding: "0.15rem 0.45rem",
                          borderRadius: "4px",
                        }}
                      >
                        {sg.count} lacking
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── 5. Institutional Capacity & Seat Gap Table ── */}
          <div style={{ backgroundColor: "#ffffff", borderRadius: "10px", border: "1px solid #e2e8f0", padding: "1.25rem", marginBottom: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div>
                <h3 style={{ fontSize: "1rem", fontWeight: "bold", color: "#0f172a", margin: 0 }}>
                  Training Capacity vs Demand Analysis
                </h3>
                <p style={{ fontSize: "0.75rem", color: "#64748b", margin: "0.2rem 0 0 0" }}>
                  Institutional seat allocations compared to community demand by block
                </p>
              </div>
              <span style={{ fontSize: "0.75rem", backgroundColor: "#fee2e2", color: "#991b1b", padding: "0.25rem 0.5rem", borderRadius: "4px", fontWeight: 600 }}>
                Shortfalls highlighted in red
              </span>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", color: "#475569" }}>
                    <th style={{ padding: "0.6rem" }}>Block</th>
                    <th style={{ padding: "0.6rem" }}>Trade</th>
                    <th style={{ padding: "0.6rem", textAlign: "right" }}>Interested Profiles</th>
                    <th style={{ padding: "0.6rem", textAlign: "right" }}>Sample Seats</th>
                    <th style={{ padding: "0.6rem", textAlign: "right" }}>Capacity Gap</th>
                    <th style={{ padding: "0.6rem", textAlign: "center" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {capacity.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                        No capacity mappings found for selected criteria.
                      </td>
                    </tr>
                  ) : (
                    capacity.map((row, idx) => (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          backgroundColor: row.is_shortfall ? "#fff1f2" : "transparent",
                        }}
                      >
                        <td style={{ padding: "0.6rem", fontWeight: 600, color: "#1e293b" }}>{row.block}</td>
                        <td style={{ padding: "0.6rem", textTransform: "capitalize", color: "#334155" }}>
                          {row.trade.replace(/_/g, " ")}
                        </td>
                        <td style={{ padding: "0.6rem", textAlign: "right", fontWeight: 600 }}>
                          {row.is_suppressed ? "< 5 (suppressed)" : row.interested_count}
                        </td>
                        <td style={{ padding: "0.6rem", textAlign: "right" }}>{row.seats}</td>
                        <td
                          style={{
                            padding: "0.6rem",
                            textAlign: "right",
                            fontWeight: 700,
                            color: row.gap > 0 ? "#dc2626" : "#16a34a",
                          }}
                        >
                          {row.is_suppressed ? "—" : row.gap > 0 ? `+${row.gap}` : `${row.gap}`}
                        </td>
                        <td style={{ padding: "0.6rem", textAlign: "center" }}>
                          {row.is_shortfall ? (
                            <span style={{ fontSize: "0.75rem", backgroundColor: "#dc2626", color: "#fff", padding: "0.2rem 0.5rem", borderRadius: "9999px", fontWeight: 600 }}>
                              Shortfall
                            </span>
                          ) : (
                            <span style={{ fontSize: "0.75rem", backgroundColor: "#dcfce7", color: "#166534", padding: "0.2rem 0.5rem", borderRadius: "9999px", fontWeight: 600 }}>
                              Sufficient
                            </span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── 6. Consented Real User Sessions (kept strictly separate) ── */}
          <div style={{ backgroundColor: "#ffffff", borderRadius: "10px", border: "1px solid #e2e8f0", padding: "1.25rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div>
                <h3 style={{ fontSize: "1rem", fontWeight: "bold", color: "#0f172a", margin: 0 }}>
                  Consented User Sessions
                </h3>
                <p style={{ fontSize: "0.75rem", color: "#64748b", margin: "0.2rem 0 0 0" }}>
                  Live user sessions where candidate opted into district official view (kept strictly separate from generated sample data)
                </p>
              </div>
              <span style={{ fontSize: "0.75rem", backgroundColor: "#dbeafe", color: "#1e40af", padding: "0.25rem 0.5rem", borderRadius: "4px", fontWeight: 600 }}>
                {consented.total_consented} Recorded
              </span>
            </div>

            {consented.sessions.length === 0 ? (
              <div style={{ padding: "1.5rem", textAlign: "center", color: "#94a3b8", fontSize: "0.85rem", backgroundColor: "#f8fafc", borderRadius: "6px" }}>
                No live users have opted into the official view yet. (Users can opt in via the consent page).
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0.75rem" }}>
                {consented.sessions.map((s, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: "0.75rem 1rem",
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      backgroundColor: "#f8fafc",
                      fontSize: "0.8rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b", marginBottom: "0.4rem" }}>
                      <code>{s.session_id_masked}</code>
                      <span>Lang: {s.language}</span>
                    </div>
                    <div style={{ fontWeight: 600, color: "#1e293b", marginBottom: "0.25rem" }}>
                      Education: {s.education}
                    </div>
                    <div style={{ color: "#475569" }}>
                      Interests: {s.interests && s.interests.length > 0 ? s.interests.join(", ") : "None stated"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
