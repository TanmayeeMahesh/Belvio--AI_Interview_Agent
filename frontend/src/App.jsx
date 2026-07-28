import { useState, useEffect } from "react";
import Login from "./pages/Login";
import LandingPage from "./pages/LandingPage";
import SuperAdminDashboard from "./pages/SuperAdminDashboard";
import CreateOrganization from "./pages/CreateOrganization";
import UserProfile from "./pages/UserProfile";
import OrgAdminDashboard from "./pages/OrgAdminDashboard";
import HRDashboard from "./pages/HRDashboard";
import HRManagement from "./pages/HRManagement";
import JobOpenings from "./pages/JobOpenings";
import JobDetails from "./pages/JobDetails";
import Candidates from "./pages/Candidates";
import Interviews from "./pages/Interviews";
import Reports from "./pages/Reports";
import OrgSettings from "./pages/OrgSettings";
import API, { setAuthToken } from "./api";

const TOKEN_KEY = "ib_token";
const EMAIL_KEY = "ib_email";

function Nav({ tab, setTab, email, role, orgName, onLogout }) {
  let tabs = [];

  if (role === "SUPER_ADMIN") {
    tabs = [
      { id: "dashboard", label: "Dashboard" },
      { id: "create-org", label: "Create Organization" },
    ];
  }

  if (role === "ORG_ADMIN") {
    tabs = [
      { id: "dashboard", label: "Dashboard" },
      { id: "hrs", label: "HR Management" },
      { id: "jobs", label: "Job Openings" },
      { id: "candidates", label: "Candidates" },
      { id: "reports", label: "Reports" },
    ];
  }

  if (role === "HR") {
    tabs = [
      { id: "dashboard", label: "Dashboard" },
      { id: "jobs", label: "Job Openings" },
      { id: "candidates", label: "Candidates" },
      { id: "interviews", label: "Interviews" },
      { id: "reports", label: "Reports" },
    ];
  }

  return (
    <nav
      style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      <div
        style={{
          width: "100%",
          padding: "0 24px",
          height: 88,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          <span style={{ fontWeight: 800, fontSize: 34, letterSpacing: "-.04em", color: "var(--primary)" }}>
            Belvio
          </span>
          <div style={{ display: "flex", gap: 4 }}>
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  border: "none",
                  padding: "10px 18px",
                  borderRadius: 8,
                  cursor: "pointer",
                  fontSize: 16,
                  fontWeight: tab === t.id ? 700 : 600,
                  color: tab === t.id ? "var(--primary)" : "var(--text-secondary)",
                  background: tab === t.id ? "rgba(37, 99, 235, 0.1)" : "transparent",
                  transition: "all 0.2s"
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
        
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          {/* Action Buttons (Settings, Profile) */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, borderRight: "1px solid var(--border)", paddingRight: 24 }}>
            {role === "ORG_ADMIN" && (
              <button 
                onClick={() => setTab("settings")}
                style={{
                  background: tab === "settings" ? "rgba(0,0,0,0.05)" : "transparent",
                  border: "1px solid transparent",
                  borderRadius: 8,
                  padding: "8px 16px",
                  cursor: "pointer",
                  color: "var(--text)",
                  fontWeight: 600,
                  fontSize: 14,
                  transition: "all 0.2s"
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(0,0,0,0.05)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = tab === "settings" ? "rgba(0,0,0,0.05)" : "transparent"; }}
              >
                Settings
              </button>
            )}
            <button 
              onClick={() => setTab("profile")}
              style={{
                background: tab === "profile" ? "rgba(0,0,0,0.05)" : "transparent",
                border: "1px solid transparent",
                borderRadius: 8,
                padding: "8px 16px",
                cursor: "pointer",
                color: "var(--text)",
                fontWeight: 600,
                fontSize: 14,
                transition: "all 0.2s"
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(0,0,0,0.05)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = tab === "profile" ? "rgba(0,0,0,0.05)" : "transparent"; }}
            >
              My Profile
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 16 }}>
              {email ? email.charAt(0).toUpperCase() : "U"}
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
              <span style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.2 }}>{email}</span>
              <span style={{ fontSize: 11, color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em" }}>
                {orgName ? `${orgName} • ${role?.replace("_", " ")}` : role?.replace("_", " ")}
              </span>
            </div>
          </div>
          
          <button 
            onClick={onLogout}
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "8px 16px",
              cursor: "pointer",
              color: "var(--danger)",
              fontWeight: 600,
              fontSize: 14,
              transition: "all 0.2s"
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--danger)"; e.currentTarget.style.color = "#fff"; e.currentTarget.style.borderColor = "var(--danger)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--danger)"; e.currentTarget.style.borderColor = "var(--border)"; }}
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem(TOKEN_KEY) || "",
  );
  const [email, setEmail] = useState(
    () => localStorage.getItem(EMAIL_KEY) || "",
  );
  const [role, setRole] = useState(null);
  const [orgName, setOrgName] = useState("");
  const [tab, setTab] = useState("dashboard");
  const [loadingUser, setLoadingUser] = useState(false);
  const [showLogin, setShowLogin] = useState(false);

  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedJobName, setSelectedJobName] = useState("");
  const [reportSessionId, setReportSessionId] = useState(null);

  const openJob = (id, name) => {
    setSelectedJobId(id);
    setSelectedJobName(name);
    setTab("job-details");
  };

  const openReport = (sessionId) => {
    setReportSessionId(sessionId);
    setTab("reports");
  };

  useEffect(() => {
    if (token) {
      setAuthToken(token);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    setLoadingUser(true);
    API.get("/api/whoami")
      .then((res) => {
        setRole(res.data.role);
        setOrgName(res.data.organization_name);
      })
      .catch((err) => {
        console.error("WHOAMI ERROR =", err);
      })
      .finally(() => {
        setLoadingUser(false);
      });
  }, [token]);

  function handleLogin(tok, em) {
    localStorage.setItem(TOKEN_KEY, tok);
    localStorage.setItem(EMAIL_KEY, em);
    setToken(tok);
    setEmail(em);
    setAuthToken(tok);
    window.location.reload();
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    setToken("");
    setEmail("");
    setAuthToken(null);
    window.location.reload();
  }

  if (loadingUser) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center" }}>
        Loading...
      </div>
    );
  }

  if (!token) {
    if (showLogin) {
      return <Login onLogin={handleLogin} />;
    }
    return <LandingPage onLoginClick={() => setShowLogin(true)} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <Nav
        tab={tab}
        setTab={setTab}
        email={email}
        onLogout={handleLogout}
        role={role}
        orgName={orgName}
      />
      
      <main style={{ flex: 1 }}>
        {tab === "profile" && <UserProfile role={role} initialEmail={email} />}
        
        {tab === "dashboard" && role === "SUPER_ADMIN" && <SuperAdminDashboard />}
        {tab === "create-org" && role === "SUPER_ADMIN" && <CreateOrganization />}
        
        {tab === "dashboard" && role === "ORG_ADMIN" && <OrgAdminDashboard onNavigate={setTab} onOpenJob={openJob} />}
        {tab === "settings" && role === "ORG_ADMIN" && <OrgSettings />}

        {tab === "dashboard" && role === "HR" && <HRDashboard onOpenJob={openJob} />}
        {tab === "jobs" && <JobOpenings onOpenJob={openJob} />}
        {tab === "hrs" && <HRManagement />}
        {tab === "candidates" && <Candidates role={role} />}
        {tab === "interviews" && <Interviews onViewReport={openReport} />}
        {tab === "job-details" && <JobDetails jobId={selectedJobId} jobName={selectedJobName} role={role} />}
        
        {tab === "reports" && <Reports token={token} defaultSessionId={reportSessionId} />}
      </main>

      <footer style={{ textAlign: "center", padding: "24px", background: "var(--surface)", borderTop: "1px solid var(--border)", width: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, fontSize: 14, color: "var(--text-secondary)", fontWeight: 500 }}>
          <span>Powered by</span>
          <img src="/bellurbis-logo.png" alt="Bellurbis" style={{ height: 44, filter: "brightness(0)", opacity: 0.8 }} />
        </div>
      </footer>
    </div>
  );
}
