import React from "react";
import LandingNavbar from "../components/landing/LandingNavbar";
import HeroSection from "../components/landing/HeroSection";
import TrustedBy from "../components/landing/TrustedBy";
import WhyBelvio from "../components/landing/WhyBelvio";
import HowItWorks from "../components/landing/HowItWorks";
import FeaturesSection from "../components/landing/FeaturesSection";
import DashboardPreview from "../components/landing/DashboardPreview";
import StatsSection from "../components/landing/StatsSection";
import InterviewDemo from "../components/landing/InterviewDemo";
import SecuritySection from "../components/landing/SecuritySection";
import Testimonials from "../components/landing/Testimonials";
import FAQ from "../components/landing/FAQ";
import Footer from "../components/landing/Footer";

/* ---------- shared theme backdrop: same system as the Login page ---------- */
function BelvioBackdrop() {
  const lines = [
    {
      d: "M-100,120 C 250,20 550,220 900,110 S 1500,40 1800,140",
      color: "#5EEAD4",
      opacity: 0.16,
      width: 1.6,
    },
    {
      d: "M-100,260 C 300,340 600,140 950,260 S 1500,360 1800,250",
      color: "#60A5FA",
      opacity: 0.1,
      width: 1.3,
    },
    {
      d: "M-100,760 C 280,650 620,880 960,730 S 1520,610 1800,750",
      color: "#5EEAD4",
      opacity: 0.14,
      width: 1.6,
    },
  ];
  const dots = [
    [90, 95, 4],
    [1500, 130, 4],
    [200, 780, 3],
    [1420, 800, 4],
    [760, 60, 3],
    [1050, 870, 3],
  ];
  return (
    <div
      aria-hidden
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
        overflow: "hidden",
      }}
    >
      {/* dot-grid texture */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "radial-gradient(circle, rgba(94,234,212,0.10) 1.2px, transparent 1.6px)",
          backgroundSize: "24px 24px",
          backgroundPosition: "-12px -12px",
        }}
      />

      {/* glow blobs */}
      <div
        style={{
          position: "absolute",
          width: 560,
          height: 560,
          top: -180,
          left: -180,
          borderRadius: "50%",
          background: "#2DD4BF",
          opacity: 0.14,
          filter: "blur(120px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 480,
          height: 480,
          bottom: -160,
          right: -140,
          borderRadius: "50%",
          background: "#1D4ED8",
          opacity: 0.16,
          filter: "blur(120px)",
        }}
      />

      {/* flowing waveform lines */}
      <svg
        viewBox="0 0 1700 900"
        preserveAspectRatio="xMidYMid slice"
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
        }}
      >
        {lines.map((l, i) => (
          <path
            key={i}
            d={l.d}
            fill="none"
            stroke={l.color}
            strokeOpacity={l.opacity}
            strokeWidth={l.width}
          />
        ))}
        {dots.map((pt, i) => (
          <circle
            key={i}
            cx={pt[0]}
            cy={pt[1]}
            r={pt[2]}
            fill="#5EEAD4"
            opacity={0.18}
          />
        ))}
      </svg>
    </div>
  );
}

export default function LandingPage({ onLoginClick }) {
  return (
    <div
      style={{
        fontFamily: "var(--font-body)",
        color: "#fff",
        background: "#0F172A",
        minHeight: "100vh",
        overflowX: "hidden",
        position: "relative",
      }}
    >
      <BelvioBackdrop />

      {/* all real content sits above the fixed backdrop */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <LandingNavbar onLoginClick={onLoginClick} />
        <HeroSection onLoginClick={onLoginClick} />
        <TrustedBy />
        <WhyBelvio />
        <HowItWorks />
        <FeaturesSection />
        <DashboardPreview />
        <StatsSection />
        <InterviewDemo />
        <SecuritySection />
        <Testimonials />
        <FAQ />
        <Footer onLoginClick={onLoginClick} />
      </div>
    </div>
  );
}
