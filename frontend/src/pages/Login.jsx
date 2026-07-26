import { useState } from "react";
import API from "../api";

/* ---------- small inline icons (no extra deps) ---------- */
function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"
        stroke="#64748B"
        strokeWidth="1.6"
      />
      <circle cx="12" cy="12" r="3" stroke="#64748B" strokeWidth="1.6" />
    </svg>
  );
}
function EyeOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"
        stroke="#64748B"
        strokeWidth="1.6"
      />
      <circle cx="12" cy="12" r="3" stroke="#64748B" strokeWidth="1.6" />
      <path d="M3 3l18 18" stroke="#64748B" strokeWidth="1.6" />
    </svg>
  );
}
function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48">
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3C33.7 32.4 29.3 35 24 35c-6.1 0-11-4.9-11-11s4.9-11 11-11c2.8 0 5.3 1 7.3 2.7l6-6C33.9 6.5 29.2 4.5 24 4.5 13.2 4.5 4.5 13.2 4.5 24S13.2 43.5 24 43.5 43.5 34.8 43.5 24c0-1.2-.1-2.4-.4-3.5Z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.6 16 18.9 13 24 13c2.8 0 5.3 1 7.3 2.7l6-6C33.9 6.5 29.2 4.5 24 4.5c-7.6 0-14.1 4.3-17.7 10.2Z"
      />
      <path
        fill="#4CAF50"
        d="M24 43.5c5.1 0 9.7-1.9 13.2-5.2l-6.1-5.2C29.2 34.6 26.7 35.5 24 35.5c-5.2 0-9.6-3.3-11.2-7.9l-6.5 5C9.7 39 16.3 43.5 24 43.5Z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.2 5.6l6.1 5.2C40.7 36 43.5 30.5 43.5 24c0-1.2-.1-2.4-.4-3.5Z"
      />
    </svg>
  );
}
function MicrosoftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 23 23">
      <rect x="1" y="1" width="10" height="10" fill="#F35325" />
      <rect x="12" y="1" width="10" height="10" fill="#81BC06" />
      <rect x="1" y="12" width="10" height="10" fill="#05A6F0" />
      <rect x="12" y="12" width="10" height="10" fill="#FFBA08" />
    </svg>
  );
}

/* ---------- full-bleed background art: bolder flowing waveform lines ---------- */
function BackgroundArt() {
  const lines = [
    {
      d: "M-100,120 C 250,20 550,220 900,110 S 1500,40 1800,140",
      color: "#0D9488",
      opacity: 0.28,
      width: 2.4,
    },
    {
      d: "M-100,200 C 300,300 600,90 950,220 S 1500,320 1800,200",
      color: "#1D4ED8",
      opacity: 0.14,
      width: 1.8,
    },
    {
      d: "M-100,700 C 280,590 620,830 960,690 S 1520,580 1800,710",
      color: "#0D9488",
      opacity: 0.26,
      width: 2.4,
    },
    {
      d: "M-100,810 C 320,900 640,740 980,850 S 1480,940 1800,800",
      color: "#1D4ED8",
      opacity: 0.12,
      width: 1.8,
    },
  ];
  const dots = [
    [90, 95, 5],
    [1500, 130, 4],
    [200, 780, 4],
    [1420, 800, 5],
    [760, 60, 3],
    [1050, 870, 4],
    [1620, 460, 3],
    [60, 460, 3],
  ];
  return (
    <svg
      viewBox="0 0 1700 900"
      preserveAspectRatio="xMidYMid slice"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        zIndex: 0,
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
          fill="#0D9488"
          opacity={0.22}
        />
      ))}
    </svg>
  );
}

/* ---------- signature illustration: a "listening" AI waveform, extruded bars for a 3D read ---------- */
function VoiceWaveIllustration() {
  const bars = [10, 18, 28, 40, 54, 40, 60, 40, 54, 40, 28, 18, 10];
  return (
    <svg
      viewBox="0 0 360 460"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <radialGradient id="glow" cx="50%" cy="34%" r="55%">
          <stop offset="0%" stopColor="#2DD4BF" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#2DD4BF" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="panelGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#052E2B" />
          <stop offset="55%" stopColor="#0B4A45" />
          <stop offset="100%" stopColor="#115E59" />
        </linearGradient>
        <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#99F6E4" />
          <stop offset="100%" stopColor="#0F766E" />
        </linearGradient>
        <linearGradient id="barGradActive" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F0FDFA" />
          <stop offset="100%" stopColor="#2DD4BF" />
        </linearGradient>
        <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
          <path
            d="M0 26V0h26"
            fill="none"
            stroke="#5EEAD4"
            strokeOpacity="0.06"
          />
        </pattern>
        <filter id="barShadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow
            dx="0"
            dy="3"
            stdDeviation="3"
            floodColor="#000"
            floodOpacity="0.35"
          />
        </filter>
      </defs>

      <rect width="360" height="460" fill="url(#panelGrad)" />
      <rect width="360" height="460" fill="url(#grid)" />
      <circle cx="180" cy="150" r="150" fill="url(#glow)" />

      <ellipse
        cx="180"
        cy="140"
        rx="118"
        ry="118"
        stroke="#5EEAD4"
        strokeOpacity="0.18"
        strokeWidth="1"
        fill="none"
      />

      <g className="pulse-dot">
        <circle cx="180" cy="60" r="5" fill="#5EEAD4" />
      </g>
      <g className="pulse-dot" style={{ animationDelay: "0.4s" }}>
        <circle cx="248" cy="95" r="4" fill="#5EEAD4" opacity="0.85" />
      </g>
      <g className="pulse-dot" style={{ animationDelay: "0.8s" }}>
        <circle cx="112" cy="95" r="4" fill="#5EEAD4" opacity="0.85" />
      </g>

      {/* waveform bars: extruded look via gradient fill + drop shadow */}
      <g transform="translate(40,215)" filter="url(#barShadow)">
        {bars.map((h, i) => (
          <rect
            key={i}
            x={i * 22}
            y={(64 - h) / 2}
            width="10"
            height={h}
            rx="5"
            fill={i === 6 ? "url(#barGradActive)" : "url(#barGrad)"}
          />
        ))}
      </g>

      <path
        d="M110 460c0-58 32-98 70-98s70 40 70 98"
        fill="#052E2B"
        opacity="0.65"
      />
      <circle cx="180" cy="332" r="40" fill="#052E2B" opacity="0.65" />
    </svg>
  );
}

export default function Login({ onLogin }) {
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [tilt, setTilt] = useState({ rx: 0, ry: 0 });

  function handleCardMouseMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({ rx: y * -6, ry: x * 8 });
  }
  function handleCardMouseLeave() {
    setTilt({ rx: 0, ry: 0 });
  }

  async function handleCheckEmail(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { data } = await API.post("/api/auth/check-email", { email });
      if (data.status === "PENDING") {
        setStep("set_password");
      } else {
        setStep("password");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Email not found.");
    }
    setLoading(false);
  }

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { data } = await API.post("/api/auth/login", { email, password });
      onLogin(data.token, data.email);
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed.");
    }
    setLoading(false);
  }

  async function handleCreatePassword(e) {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await API.post("/api/auth/complete-registration", { email, password });
      const { data } = await API.post("/api/auth/login", { email, password });
      onLogin(data.token, data.email);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to set password.");
    }
    setLoading(false);
  }

  const fieldWrap = { display: "flex", flexDirection: "column", gap: 6 };
  const labelStyle = { fontSize: 13, fontWeight: 600, color: "#334155" };
  const inputStyle = {
    background: "#F8FAFC",
    color: "#0F172A",
    border: "1px solid #E2E8F0",
    borderRadius: 12,
    height: 46,
    padding: "0 16px",
    fontSize: 15,
    width: "100%",
    outline: "none",
    boxSizing: "border-box",
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        background: "#EEF2F6",
        overflow: "hidden",
        perspective: "1600px",
      }}
    >
      <style>{`
        .belvio-page-bg {
          position: absolute;
          inset: 0;
          background-image: radial-gradient(circle, rgba(15,23,42,0.08) 1.2px, transparent 1.6px);
          background-size: 24px 24px;
          background-position: -12px -12px;
          z-index: 0;
        }
        .belvio-blob { position: absolute; border-radius: 50%; filter: blur(90px); z-index: 0; }
        .belvio-input:focus { border-color: #0D9488 !important; box-shadow: 0 0 0 3px rgba(13,148,136,0.15); }
        .belvio-btn-primary {
          background: #0F172A; color: #fff; border: none; border-radius: 12px; height: 48px;
          font-size: 15px; font-weight: 600; cursor: pointer;
          transition: background 0.15s ease, transform 0.05s ease;
          box-shadow: 0 10px 20px -8px rgba(15,23,42,0.5);
        }
        .belvio-btn-primary:hover { background: #1E293B; }
        .belvio-btn-primary:active { transform: scale(0.99); }
        .belvio-btn-primary:disabled { opacity: 0.6; cursor: default; }
        .belvio-sso-btn {
          flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px; height: 44px;
          border-radius: 12px; border: 1px solid #E2E8F0; background: #fff; font-size: 14px; font-weight: 500;
          color: #334155; cursor: pointer; transition: border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
        }
        .belvio-sso-btn:hover { background: #F8FAFC; border-color: #CBD5E1; transform: translateY(-1px); }
        .belvio-eye-btn {
          position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
          background: none; border: none; cursor: pointer; display: flex; align-items: center;
        }
        .pulse-dot { animation: belvioPulse 1.8s ease-in-out infinite; transform-origin: center; }
        @keyframes belvioPulse {
          0%, 100% { opacity: 0.35; transform: scale(0.85); }
          50% { opacity: 1; transform: scale(1.1); }
        }
        @media (prefers-reduced-motion: reduce) { .pulse-dot { animation: none; } }
        @media (max-width: 860px) { .belvio-illustration-panel { display: none; } }
      `}</style>

      <div className="belvio-page-bg" />
      <BackgroundArt />
      <div
        className="belvio-blob"
        style={{
          width: 520,
          height: 520,
          top: -160,
          left: -160,
          background: "#2DD4BF",
          opacity: 0.24,
        }}
      />
      <div
        className="belvio-blob"
        style={{
          width: 460,
          height: 460,
          bottom: -180,
          right: -140,
          background: "#1D4ED8",
          opacity: 0.18,
        }}
      />

      <div
        style={{
          position: "relative",
          zIndex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 28,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.08em",
            color: "#0D9488",
            textTransform: "uppercase",
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "#0D9488",
              display: "inline-block",
            }}
          />
          Belvio &middot; AI Interview Platform
        </div>

        {/* grounding shadow beneath the floating card */}
        <div
          style={{
            position: "absolute",
            top: "58%",
            width: "min(880px, 84vw)",
            height: 80,
            background:
              "radial-gradient(ellipse, rgba(15,23,42,0.35) 0%, transparent 70%)",
            filter: "blur(10px)",
            zIndex: 0,
          }}
        />

        <div
          onMouseMove={handleCardMouseMove}
          onMouseLeave={handleCardMouseLeave}
          style={{
            width: "min(960px, 92vw)",
            minHeight: 560,
            display: "flex",
            background: "#fff",
            borderRadius: 28,
            overflow: "hidden",
            border: "1px solid rgba(15,23,42,0.06)",
            boxShadow:
              "0 50px 100px -30px rgba(15,23,42,0.45), 0 16px 32px -12px rgba(15,23,42,0.18), inset 0 1px 0 rgba(255,255,255,0.6)",
            transformStyle: "preserve-3d",
            transform: `rotateX(${tilt.rx}deg) rotateY(${tilt.ry}deg)`,
            transition: "transform 0.2s ease-out",
            position: "relative",
            zIndex: 1,
          }}
        >
          <div
            className="belvio-illustration-panel"
            style={{
              flex: "0 0 42%",
              position: "relative",
              transform: "translateZ(20px)",
            }}
          >
            <VoiceWaveIllustration />

            <div
              style={{
                position: "absolute",
                top: 28,
                left: 28,
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 12px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.12)",
                border: "1px solid rgba(255,255,255,0.25)",
                backdropFilter: "blur(6px)",
                color: "#F0FDFA",
                fontSize: 12,
                fontWeight: 500,
                boxShadow: "0 8px 20px -6px rgba(0,0,0,0.4)",
                transform: "translateZ(50px)",
              }}
            >
              <span
                className="pulse-dot"
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "#5EEAD4",
                  display: "inline-block",
                }}
              />
              Listening
            </div>

            <div
              style={{
                position: "absolute",
                left: 32,
                bottom: 32,
                color: "#fff",
                transform: "translateZ(40px)",
              }}
            >
              <div
                style={{
                  fontSize: 23,
                  fontWeight: 700,
                  letterSpacing: "-0.01em",
                }}
              >
                Belvio AI
              </div>
              <div
                style={{
                  fontSize: 13,
                  opacity: 0.75,
                  marginTop: 4,
                  maxWidth: 220,
                  lineHeight: 1.5,
                }}
              >
                Autonomous interviews. Human-level judgment.
              </div>
            </div>
          </div>

          <div
            style={{
              flex: "1 1 auto",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              padding: "56px 64px",
              gap: 24,
              transform: "translateZ(30px)",
            }}
          >
            <div>
              <h1
                style={{
                  fontSize: 32,
                  fontWeight: 700,
                  margin: 0,
                  color: "#0F172A",
                  letterSpacing: "-0.02em",
                }}
              >
                Log in
              </h1>
              <p style={{ fontSize: 14, color: "#64748B", marginTop: 8 }}>
                Sign in to your Belvio interview dashboard.
              </p>
            </div>

            {step === "email" && (
              <form
                onSubmit={handleCheckEmail}
                style={{ display: "flex", flexDirection: "column", gap: 18 }}
              >
                <div style={fieldWrap}>
                  <label style={labelStyle}>Email address</label>
                  <input
                    className="belvio-input"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    style={inputStyle}
                  />
                </div>
                {error && (
                  <div style={{ color: "#DC2626", fontSize: 13 }}>{error}</div>
                )}
                <button
                  type="submit"
                  className="belvio-btn-primary"
                  disabled={loading}
                >
                  {loading ? "Checking..." : "Continue"}
                </button>
              </form>
            )}

            {step === "password" && (
              <form
                onSubmit={handleLogin}
                style={{ display: "flex", flexDirection: "column", gap: 18 }}
              >
                <div>
                  <div style={{ fontSize: 14, color: "#334155" }}>
                    Welcome back, <strong>{email}</strong>
                  </div>
                  <button
                    type="button"
                    onClick={() => setStep("email")}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#0D9488",
                      cursor: "pointer",
                      fontSize: 12,
                      padding: 0,
                      marginTop: 4,
                    }}
                  >
                    Not you? Change email
                  </button>
                </div>
                <div style={fieldWrap}>
                  <label style={labelStyle}>Password</label>
                  <div style={{ position: "relative" }}>
                    <input
                      className="belvio-input"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                      style={{ ...inputStyle, paddingRight: 44 }}
                    />
                    <button
                      type="button"
                      className="belvio-eye-btn"
                      onClick={() => setShowPassword((s) => !s)}
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
                    >
                      {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                    </button>
                  </div>
                </div>
                {error && (
                  <div style={{ color: "#DC2626", fontSize: 13 }}>{error}</div>
                )}
                <button
                  type="submit"
                  className="belvio-btn-primary"
                  disabled={loading}
                >
                  {loading ? "Signing in..." : "Sign in"}
                </button>
                <div style={{ textAlign: "center" }}>
                  <a
                    href="#"
                    style={{
                      fontSize: 13,
                      color: "#0D9488",
                      textDecoration: "none",
                    }}
                  >
                    Forgot your password?
                  </a>
                </div>
              </form>
            )}

            {step === "set_password" && (
              <form
                onSubmit={handleCreatePassword}
                style={{ display: "flex", flexDirection: "column", gap: 18 }}
              >
                <div>
                  <label style={labelStyle}>Set your password</label>
                  <p
                    style={{
                      fontSize: 13,
                      color: "#64748B",
                      margin: "4px 0 0",
                    }}
                  >
                    Looks like it's your first time logging in. Please set a
                    password for <strong>{email}</strong>.
                  </p>
                </div>
                <div style={fieldWrap}>
                  <label style={labelStyle}>New password</label>
                  <input
                    className="belvio-input"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    style={inputStyle}
                  />
                </div>
                <div style={fieldWrap}>
                  <label style={labelStyle}>Confirm password</label>
                  <input
                    className="belvio-input"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    style={inputStyle}
                  />
                </div>
                {error && (
                  <div style={{ color: "#DC2626", fontSize: 13 }}>{error}</div>
                )}
                <button
                  type="submit"
                  className="belvio-btn-primary"
                  disabled={loading}
                >
                  {loading ? "Saving..." : "Save password & sign in"}
                </button>
              </form>
            )}

            {step === "email" && (
              <>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    margin: "4px 0",
                  }}
                >
                  <div style={{ flex: 1, height: 1, background: "#E2E8F0" }} />
                  <span style={{ fontSize: 12, color: "#94A3B8" }}>
                    or continue with
                  </span>
                  <div style={{ flex: 1, height: 1, background: "#E2E8F0" }} />
                </div>
                <div style={{ display: "flex", gap: 12 }}>
                  <button type="button" className="belvio-sso-btn">
                    <GoogleIcon /> Google
                  </button>
                  <button type="button" className="belvio-sso-btn">
                    <MicrosoftIcon /> Microsoft
                  </button>
                </div>
              </>
            )}

            <p
              style={{
                fontSize: 12,
                color: "#94A3B8",
                textAlign: "center",
                margin: 0,
              }}
            >
              Powered by <strong>Bellurbis Technologies</strong>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
