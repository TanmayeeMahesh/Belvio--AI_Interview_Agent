import React from "react";

export default function LandingNavbar({ onLoginClick }) {
  return (
    <nav style={{ 
      display: "flex", 
      justifyContent: "space-between", 
      alignItems: "center", 
      padding: "20px 48px", 
      background: "rgba(15, 23, 42, 0.85)", 
      backdropFilter: "blur(12px)", 
      position: "sticky", 
      top: 0, 
      zIndex: 50, 
      borderBottom: "1px solid rgba(255,255,255,0.1)" 
    }}>
      <div style={{ fontSize: 24, fontWeight: "bold", fontFamily: "var(--font-heading)", letterSpacing: "-0.02em", color: "#fff" }}>
        Belvio<span style={{ color: "var(--primary)" }}>.ai</span>
      </div>
      
      <div style={{ display: "flex", gap: 32, color: "rgba(255,255,255,0.8)", fontSize: 14, fontWeight: 500 }}>
        <span style={{ cursor: "pointer", transition: "color 0.2s" }} onMouseEnter={(e) => e.target.style.color = "#fff"} onMouseLeave={(e) => e.target.style.color = "rgba(255,255,255,0.8)"}>Features</span>
        <span style={{ cursor: "pointer", transition: "color 0.2s" }} onMouseEnter={(e) => e.target.style.color = "#fff"} onMouseLeave={(e) => e.target.style.color = "rgba(255,255,255,0.8)"}>How It Works</span>
        <span style={{ cursor: "pointer", transition: "color 0.2s" }} onMouseEnter={(e) => e.target.style.color = "#fff"} onMouseLeave={(e) => e.target.style.color = "rgba(255,255,255,0.8)"}>Solutions</span>
        <span style={{ cursor: "pointer", transition: "color 0.2s" }} onMouseEnter={(e) => e.target.style.color = "#fff"} onMouseLeave={(e) => e.target.style.color = "rgba(255,255,255,0.8)"}>Pricing</span>
        <span style={{ cursor: "pointer", transition: "color 0.2s" }} onMouseEnter={(e) => e.target.style.color = "#fff"} onMouseLeave={(e) => e.target.style.color = "rgba(255,255,255,0.8)"}>About</span>
        <span style={{ cursor: "pointer", transition: "color 0.2s" }} onMouseEnter={(e) => e.target.style.color = "#fff"} onMouseLeave={(e) => e.target.style.color = "rgba(255,255,255,0.8)"}>Contact</span>
      </div>

      <div style={{ display: "flex", gap: 16 }}>
        <button style={{ background: "transparent", color: "#fff", border: "1px solid rgba(255,255,255,0.2)", padding: "8px 16px", borderRadius: 8 }} onClick={onLoginClick}>
          Login
        </button>
        <button onClick={onLoginClick} style={{ background: "var(--primary)", color: "#fff", border: "none", padding: "8px 16px", borderRadius: 8, fontWeight: 600 }}>
          Request Demo
        </button>
      </div>
    </nav>
  );
}
