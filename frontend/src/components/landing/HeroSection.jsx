import React from "react";

function PulseDot({ color = "#5EEAD4" }) {
  return (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: color,
        display: "inline-block",
        animation: "belvioHeroPulse 1.8s ease-in-out infinite",
      }}
    />
  );
}

export default function HeroSection({ onLoginClick }) {
  return (
    <header
      style={{
        position: "relative",
        padding: "140px 24px 120px",
        textAlign: "center",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      <style>{`
        @keyframes belvioHeroPulse {
          0%, 100% { opacity: 0.35; transform: scale(0.85); }
          50% { opacity: 1; transform: scale(1.1); }
        }
        .belvio-hero-primary {
          background: linear-gradient(135deg, #0D9488, #2563EB);
          transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .belvio-hero-primary:hover { transform: translateY(-2px); box-shadow: 0 16px 32px -8px rgba(13,148,136,0.55); }
        .belvio-hero-secondary { transition: background 0.15s ease, transform 0.15s ease; }
        .belvio-hero-secondary:hover { background: rgba(255,255,255,0.16); transform: translateY(-2px); }
        .belvio-hero-tertiary { transition: color 0.15s ease, gap 0.15s ease; }
        .belvio-hero-tertiary:hover { color: #5EEAD4; }
        @media (prefers-reduced-motion: reduce) {
          .belvio-hero-pulse { animation: none !important; }
        }
      `}</style>

      {/* faded product photo, kept but tuned down */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: "url('/ai_interview_bot_bg.png')",
          backgroundSize: "cover",
          backgroundPosition: "center",
          opacity: 0.12,
          zIndex: 0,
        }}
      />

      {/* teal/navy gradient wash so the photo blends into the brand palette */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(15,23,42,0.2) 0%, rgba(15,23,42,0.75) 75%)",
          zIndex: 1,
        }}
      />

      {/* soft glow behind the headline, echoes the login illustration panel */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          top: "8%",
          left: "50%",
          width: 900,
          height: 500,
          transform: "translateX(-50%)",
          background:
            "radial-gradient(ellipse, rgba(45,212,191,0.22) 0%, transparent 70%)",
          filter: "blur(50px)",
          zIndex: 1,
          pointerEvents: "none",
        }}
      />

      <div style={{ position: "relative", zIndex: 2, maxWidth: 900 }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.08em",
            color: "#5EEAD4",
            textTransform: "uppercase",
            marginBottom: 24,
            padding: "6px 14px",
            borderRadius: 999,
            background: "rgba(94,234,212,0.08)",
            border: "1px solid rgba(94,234,212,0.2)",
          }}
        >
          <PulseDot />
          Autonomous AI Interview Platform
        </div>

        <h1
          style={{
            fontSize: 56,
            fontWeight: 800,
            lineHeight: 1.1,
            marginBottom: 24,
            letterSpacing: "-0.03em",
            color: "#fff",
          }}
        >
          AI Interviews. Smarter Hiring. <br />{" "}
          <span
            style={{
              background: "linear-gradient(135deg, #5EEAD4, #60A5FA)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            Better Decisions.
          </span>
        </h1>
        <p
          style={{
            fontSize: 20,
            color: "rgba(255,255,255,0.8)",
            marginBottom: 40,
            lineHeight: 1.6,
            maxWidth: 700,
            margin: "0 auto 40px",
          }}
        >
          Automate technical interviews, evaluate candidates with AI, and help
          recruiters hire faster with confidence.
        </p>
        <div
          style={{
            display: "flex",
            gap: 16,
            justifyContent: "center",
            flexWrap: "wrap",
          }}
        >
          <button
            onClick={onLoginClick}
            className="belvio-hero-primary"
            style={{
              color: "#fff",
              border: "none",
              padding: "16px 32px",
              borderRadius: 12,
              fontSize: 16,
              fontWeight: 600,
              boxShadow: "0 10px 25px -5px rgba(13,148,136,0.5)",
              cursor: "pointer",
            }}
          >
            Get Started
          </button>

          <button
            onClick={onLoginClick}
            className="belvio-hero-secondary"
            style={{
              background: "rgba(255,255,255,0.1)",
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.2)",
              padding: "16px 32px",
              borderRadius: 12,
              fontSize: 16,
              fontWeight: 600,
              backdropFilter: "blur(8px)",
              cursor: "pointer",
            }}
          >
            Login
          </button>
          <button
            onClick={onLoginClick}
            className="belvio-hero-tertiary"
            style={{
              background: "transparent",
              color: "rgba(255,255,255,0.85)",
              border: "1px solid transparent",
              padding: "16px 32px",
              borderRadius: 12,
              fontSize: 16,
              fontWeight: 600,
              textDecoration: "underline",
              cursor: "pointer",
            }}
          >
            Request Demo
          </button>
        </div>
      </div>
    </header>
  );
}
