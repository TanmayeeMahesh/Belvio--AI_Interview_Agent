import React from "react";

export default function HowItWorks() {
  const steps = [
    "Create Job",
    "Upload Resume",
    "Schedule Interview",
    "AI Conducts Interview",
    "Evaluation",
    "Hire Candidate"
  ];

  return (
    <section style={{ padding: "100px 24px",  overflow: "hidden" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto", textAlign: "center" }}>
        <h2 style={{ fontSize: 36, marginBottom: 64, color: "#fff" }}>How It Works</h2>
        
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", position: "relative", flexWrap: "wrap", gap: 32 }}>
          {/* Connector Line */}
          <div style={{ position: "absolute", top: "24px", left: "5%", right: "5%", height: 2, background: "rgba(37,99,235,0.3)", zIndex: 0, display: "none" }} className="timeline-line"></div>
          
          {steps.map((step, i) => (
            <div key={i} style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", alignItems: "center", flex: "1 1 120px" }}>
              <div style={{ width: 50, height: 50, borderRadius: "50%", background: i === steps.length - 1 ? "var(--success)" : "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", color: "#fff", marginBottom: 16, boxShadow: "0 0 20px rgba(37,99,235,0.4)" }}>
                {i + 1}
              </div>
              <div style={{ fontWeight: 600, color: "#fff", fontSize: 15 }}>{step}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
