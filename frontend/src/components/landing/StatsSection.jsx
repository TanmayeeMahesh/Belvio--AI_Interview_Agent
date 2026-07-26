import React from "react";

export default function StatsSection() {
  const stats = [
    { value: "80%", label: "Reduction in recruiter interview time" },
    { value: "95%", label: "Consistent interview evaluation" },
    { value: "3x", label: "Faster hiring pipeline" },
    { value: "24/7", label: "AI Interview Availability" }
  ];

  return (
    <section style={{ padding: "80px 24px",  borderTop: "1px solid rgba(255,255,255,0.05)" , backdropFilter: "blur(12px)" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto", textAlign: "center" }}>
        <h2 style={{ fontSize: 32, marginBottom: 64, color: "#fff" }}>Why Companies Choose Belvio</h2>
        
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 32 }}>
          {stats.map((s, i) => (
            <div key={i} style={{ padding: 24 }}>
              <div style={{ fontSize: 56, fontWeight: 800, color: "var(--primary)", marginBottom: 16, lineHeight: 1 }}>
                {s.value}
              </div>
              <div style={{ color: "rgba(255,255,255,0.8)", fontSize: 16, fontWeight: 500 }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
