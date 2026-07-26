import React from "react";

export default function InterviewDemo() {
  return (
    <section style={{ padding: "100px 24px", }}>
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        <h2 style={{ fontSize: 36, textAlign: "center", marginBottom: 24, color: "#fff" }}>Real-time AI Interactions</h2>
        <p style={{ textAlign: "center", color: "rgba(255,255,255,0.6)", marginBottom: 64, fontSize: 18 }}>Experience how naturally our voice agent converses.</p>
        
        <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 24, padding: 32, display: "flex", flexDirection: "column", gap: 24 , backdropFilter: "blur(12px)" }}>
          {/* AI Message */}
          <div style={{ display: "flex", gap: 16, maxWidth: "80%" }}>
            <div style={{ width: 40, height: 40, borderRadius: "50%", background: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>🤖</div>
            <div style={{ background: "rgba(37,99,235,0.1)", border: "1px solid rgba(37,99,235,0.2)", borderRadius: "16px 16px 16px 0", padding: "16px 24px", color: "#fff" }}>
              <div style={{ fontWeight: 600, fontSize: 12, color: "var(--accent)", marginBottom: 8, textTransform: "uppercase" }}>Belvio AI</div>
              <div style={{ lineHeight: 1.5 }}>
                Hello John. Welcome to your Backend Developer interview. Let's begin. <br/><br/>
                Question 1: Can you explain how you would design a rate-limiting middleware in a distributed Node.js architecture?
              </div>
            </div>
          </div>
          
          {/* Candidate Message */}
          <div style={{ display: "flex", gap: 16, maxWidth: "80%", alignSelf: "flex-end", flexDirection: "row-reverse" }}>
            <div style={{ width: 40, height: 40, borderRadius: "50%", background: "rgba(255,255,255,0.1)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>👤</div>
            <div style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "16px 16px 0 16px", padding: "16px 24px", color: "#fff" , backdropFilter: "blur(12px)" }}>
              <div style={{ fontWeight: 600, fontSize: 12, color: "rgba(255,255,255,0.5)", marginBottom: 8, textTransform: "uppercase", textAlign: "right" }}>Candidate</div>
              <div style={{ lineHeight: 1.5 }}>
                Sure. In a distributed environment, I wouldn't use in-memory stores. I would use Redis to maintain a sliding window counter or token bucket...
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
