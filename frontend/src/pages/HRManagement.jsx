import { useEffect, useState } from "react";
import API from "../api";

export default function HRManagement() {
  const [hrs, setHrs] = useState([]);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("HR");
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadHRs();
  }, []);

  async function loadHRs() {
    const { data } = await API.get("/api/org-admin/hrs");
    setHrs(data);
  }

  async function createHR(e) {
    e.preventDefault();
    if (!email.trim() || !name.trim()) return;
    setLoading(true);
    try {
      await API.post("/api/org-admin/create-hr", { email, name, role });
      setEmail("");
      setName("");
      setRole("HR");
      setIsPanelOpen(false);
      loadHRs();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to create HR.");
    } finally {
      setLoading(false);
    }
  }

  async function deleteHR(userId) {
    if (!window.confirm("Are you sure you want to remove this HR account?")) return;
    try {
      await API.delete(`/api/org-admin/hr/${userId}`);
      loadHRs();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: 32 }}>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>HR Management</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>Manage HR accounts and permissions for your organization.</p>
        </div>
        <button 
          className="btn-primary flex-row" 
          onClick={() => setIsPanelOpen(true)} 
          style={{ 
            borderRadius: 16, 
            padding: "16px 24px", 
            flexDirection: "column", 
            gap: 4, 
            justifyContent: "center",
            boxShadow: "0 4px 12px rgba(37, 99, 235, 0.2)"
          }}
        >
          <span style={{ fontSize: 32, lineHeight: 1, fontWeight: 300 }}>+</span>
          <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>Add HR</span>
        </button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {hrs.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--text-secondary)" }}>
            No HR personnel found. Add an HR to get started.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th>Email</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {hrs.map((hr) => (
                <tr key={hr.id}>
                  <td className="font-semibold">{hr.name || "N/A"}</td>
                  <td>{hr.role || "HR"}</td>
                  <td>{hr.email}</td>
                  <td>
                    <span className={`badge ${hr.status === "active" ? "badge-completed" : "badge-in_progress"}`}>
                      {hr.status || "Active"}
                    </span>
                  </td>
                  <td>
                    <button className="btn-ghost btn-sm text-danger" onClick={() => deleteHR(hr.id)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {isPanelOpen && (
        <div className="slide-over-overlay" onClick={() => setIsPanelOpen(false)}>
          <div className="slide-over-panel open" onClick={e => e.stopPropagation()}>
            <div style={{ padding: "24px 32px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: 20, margin: 0 }}>Add New HR</h2>
              <button className="btn-ghost btn-sm" onClick={() => setIsPanelOpen(false)} style={{ padding: "4px 8px", fontSize: 18 }}>✕</button>
            </div>
            
            <div style={{ padding: 32, flex: 1, overflowY: "auto" }}>
              <form onSubmit={createHR} className="gap-20">
                <div>
                  <label>Full Name</label>
                  <input
                    type="text"
                    placeholder="John Doe"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label>Email Address</label>
                  <input
                    type="email"
                    placeholder="hr@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label>Role</label>
                  <select value={role} onChange={(e) => setRole(e.target.value)} required>
                    <option value="HR">HR Manager</option>
                    <option value="RECRUITER">Recruiter</option>
                    <option value="INTERVIEWER">Interviewer</option>
                    <option value="ORG_ADMIN">Organization Admin</option>
                  </select>
                  <p className="text-secondary text-sm mt-8">The user will be sent an invitation to log in.</p>
                </div>

                <div style={{ marginTop: 24 }}>
                  <button type="submit" className="btn-primary" disabled={loading} style={{ width: "100%" }}>
                    {loading ? "Adding..." : "Add HR User"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
