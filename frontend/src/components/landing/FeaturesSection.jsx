import React from "react";

export default function FeaturesSection() {
  const features = [
    { name: "Resume Parsing", icon: "📄" },
    { name: "Live Interview Bot", icon: "🤖" },
    { name: "Speech Recognition", icon: "🎙️" },
    { name: "Candidate Reports", icon: "📋" },
    { name: "Organization Management", icon: "🏢" },
    { name: "Role Based Access", icon: "🔐" },
    { name: "Hiring Analytics", icon: "📊" },
    { name: "Email Scheduling", icon: "✉️" }
  ];

  return (
    <section style={{ padding: "100px 24px", }}>
      <div style={{ maxWidth: 1000, margin: "0 auto" }}>
        <h2 style={{ fontSize: 36, textAlign: "center", marginBottom: 64, color: "#fff" }}>Product Features</h2>
        
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 24 }}>
          {features.map((f, i) => (
            <div key={i} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", padding: "24px", borderRadius: 12, display: "flex", alignItems: "center", gap: 16 , backdropFilter: "blur(12px)" }}>
              <div style={{ fontSize: 24, background: "rgba(37,99,235,0.1)", width: 48, height: 48, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {f.icon}
              </div>
              <div style={{ fontWeight: 500, color: "rgba(255,255,255,0.9)" }}>{f.name}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
