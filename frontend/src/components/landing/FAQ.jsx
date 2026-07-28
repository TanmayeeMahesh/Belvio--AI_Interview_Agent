import React from "react";

export default function FAQ() {
  const faqs = [
    { q: "How does AI evaluate candidates?", a: "The AI agent generates a structured report analyzing the candidate's technical accuracy, problem-solving skills, and communication depth based on the transcript." },
    { q: "Does it support Teams?", a: "Currently, Belvio integrates seamlessly with Google Meet. MS Teams and Zoom integrations are on our roadmap." },
    { q: "Can I customize questions?", a: "Yes! While the AI generates customized questions based on the candidate's resume gap analysis, you can also inject custom topics." },
    { q: "Can multiple HR users collaborate?", a: "Absolutely. Belvio supports Role-Based Access Control so ORG_ADMINs and HRs can collaborate within the same organization." }
  ];

  return (
    <section style={{ padding: "100px 24px", }}>
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        <h2 style={{ fontSize: 36, textAlign: "center", marginBottom: 64, color: "#fff" }}>Frequently Asked Questions</h2>
        
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {faqs.map((f, i) => (
            <div key={i} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 16, padding: 32 , backdropFilter: "blur(12px)" }}>
              <h3 style={{ fontSize: 20, color: "#fff", marginBottom: 12 }}>{f.q}</h3>
              <p style={{ color: "rgba(255,255,255,0.6)", lineHeight: 1.6 }}>{f.a}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
