import React from "react";

export default function TrustedBy() {
  return (
    <section style={{ padding: "40px 24px 80px", textAlign: "center", position: "relative", zIndex: 2, }}>
      <p style={{ color: "rgba(255,255,255,0.5)", textTransform: "uppercase", fontSize: 13, letterSpacing: "0.1em", marginBottom: 24, fontWeight: 600 }}>
        Built for the best teams
      </p>
      <div style={{ display: "flex", justifyContent: "center", gap: 48, flexWrap: "wrap", opacity: 0.7 }}>
        {["Enterprises", "Startups", "Recruitment Agencies", "Universities"].map((brand, i) => (
          <div key={i} style={{ fontSize: 24, fontWeight: 700, fontFamily: "var(--font-heading)", color: "#fff" }}>
            {brand}
          </div>
        ))}
      </div>
    </section>
  );
}
