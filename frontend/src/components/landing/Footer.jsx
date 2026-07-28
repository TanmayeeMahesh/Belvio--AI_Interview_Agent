import React from "react";

export default function Footer({ onLoginClick }) {
  return (
    <footer style={{  padding: "80px 24px 40px", borderTop: "1px solid rgba(255,255,255,0.05)" , backdropFilter: "blur(12px)" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 48, marginBottom: 80 }}>
          <div style={{ maxWidth: 300 }}>
            <div style={{ fontSize: 24, fontWeight: "bold", fontFamily: "var(--font-heading)", letterSpacing: "-0.02em", color: "#fff", marginBottom: 16 }}>
              Belvio<span style={{ color: "var(--primary)" }}>.ai</span>
            </div>
            <p style={{ color: "rgba(255,255,255,0.5)", lineHeight: 1.6 }}>
              The future of technical hiring. Automate your screening with autonomous AI voice agents.
            </p>
          </div>
          
          <div style={{ display: "flex", gap: 80, flexWrap: "wrap" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ color: "#fff", fontWeight: 600, marginBottom: 8 }}>Product</div>
              <span style={{ color: "rgba(255,255,255,0.5)", cursor: "pointer" }}>Features</span>
              <span style={{ color: "rgba(255,255,255,0.5)", cursor: "pointer" }}>Pricing</span>
              <span style={{ color: "rgba(255,255,255,0.5)", cursor: "pointer" }} onClick={onLoginClick}>Login</span>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ color: "#fff", fontWeight: 600, marginBottom: 8 }}>Company</div>
              <span style={{ color: "rgba(255,255,255,0.5)", cursor: "pointer" }}>About</span>
              <span style={{ color: "rgba(255,255,255,0.5)", cursor: "pointer" }}>Careers</span>
              <span style={{ color: "rgba(255,255,255,0.5)", cursor: "pointer" }}>Contact</span>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ color: "#fff", fontWeight: 600, marginBottom: 8 }}>Legal</div>
              <span style={{ color: "rgba(255,255,255,0.5)", cursor: "pointer" }}>Privacy Policy</span>
              <span style={{ color: "rgba(255,255,255,0.5)", cursor: "pointer" }}>Terms of Service</span>
            </div>
          </div>
        </div>
        
        <div style={{ textAlign: "center", paddingTop: 40, borderTop: "1px solid rgba(255,255,255,0.05)" , backdropFilter: "blur(12px)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, fontSize: 14, color: "rgba(255,255,255,0.7)", fontWeight: 500, marginBottom: 16 }}>
            <span>Powered by</span>
            <img src="/bellurbis-logo.png" alt="Bellurbis" style={{ height: 44 }} />
          </div>
          <div style={{ color: "rgba(255,255,255,0.3)", fontSize: 14 }}>
            © 2026 Belvio. All rights reserved.
          </div>
        </div>
      </div>
    </footer>
  );
}
