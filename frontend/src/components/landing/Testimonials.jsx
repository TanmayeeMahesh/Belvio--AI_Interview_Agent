import React from "react";

export default function Testimonials() {
  return (
    <section style={{ padding: "100px 24px",  position: "relative" }}>
      <div style={{ maxWidth: 800, margin: "0 auto", textAlign: "center" }}>
        <div style={{ fontSize: 48, color: "var(--primary)", opacity: 0.5, marginBottom: 24 }}>"</div>
        <p style={{ fontSize: 28, fontWeight: 500, color: "#fff", lineHeight: 1.5, marginBottom: 40, fontStyle: "italic" }}>
          Reduced our interview workload by 60%. We now only talk to pre-vetted, highly qualified candidates.
        </p>
        <div style={{ fontWeight: 600, color: "var(--accent)", fontSize: 18 }}>— HR Manager</div>
      </div>
    </section>
  );
}
