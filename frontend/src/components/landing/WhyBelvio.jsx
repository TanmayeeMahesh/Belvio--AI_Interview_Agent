import React from "react";

export default function WhyBelvio() {
  return (
    <section style={{ padding: "80px 24px", }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <h2 style={{ fontSize: 36, textAlign: "center", marginBottom: 64, color: "#fff" }}>Why Belvio?</h2>
        
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 32 }}>
          {[
            { icon: "🤖", title: "AI Interview Bot", desc: "Conducts interviews automatically. Converses naturally and intelligently in real-time." },
            { icon: "🧠", title: "Resume Intelligence", desc: "Extracts skills, experience, and candidate insights instantly from any resume format." },
            { icon: "📝", title: "Smart Evaluation", desc: "Generates structured reports with AI scoring, completely free of human bias." },
            { icon: "📈", title: "Analytics", desc: "Track hiring performance, pipeline velocity, and success metrics across teams." }
          ].map((feature, i) => (
            <div key={i} style={{ background: "rgba(255,255,255,0.03)", padding: 32, borderRadius: 16, border: "1px solid rgba(255,255,255,0.05)", transition: "transform 0.2s" , backdropFilter: "blur(12px)" }} onMouseEnter={(e) => e.currentTarget.style.transform = "translateY(-4px)"} onMouseLeave={(e) => e.currentTarget.style.transform = "none"}>
              <div style={{ fontSize: 40, marginBottom: 16 }}>{feature.icon}</div>
              <h3 style={{ fontSize: 20, marginBottom: 12, color: "#fff" }}>{feature.title}</h3>
              <p style={{ color: "rgba(255,255,255,0.6)", lineHeight: 1.6 }}>{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
