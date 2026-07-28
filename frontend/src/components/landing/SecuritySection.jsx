import React from "react";

export default function SecuritySection() {
  const points = [
    "Organization Isolation",
    "Secure Authentication",
    "Role-Based Access Control",
    "Enterprise Ready",
    "Data Privacy"
  ];

  return (
    <section style={{ padding: "100px 24px", }}>
      <div style={{ maxWidth: 800, margin: "0 auto", textAlign: "center" }}>
        <h2 style={{ fontSize: 36, marginBottom: 24, color: "#fff" }}>Enterprise-Grade Security</h2>
        <p style={{ color: "rgba(255,255,255,0.6)", marginBottom: 64, fontSize: 18 }}>Your candidate data is sensitive. We treat it that way.</p>
        
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 24 }}>
          {points.map((p, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, background: "rgba(255,255,255,0.03)", padding: "16px 24px", borderRadius: 100, border: "1px solid rgba(255,255,255,0.05)" , backdropFilter: "blur(12px)" }}>
              <span style={{ color: "var(--success)", fontSize: 20 }}>✔</span>
              <span style={{ color: "#fff", fontWeight: 500 }}>{p}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
