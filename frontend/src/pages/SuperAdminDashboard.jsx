import { useEffect, useState } from "react";
import API from "../api";

export default function SuperAdminDashboard() {
  const [stats, setStats] = useState(null);
  const [orgs, setOrgs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, orgsRes] = await Promise.all([
          API.get("/api/dashboard/super-admin"),
          API.get("/api/admin/organizations")
        ]);
        setStats(statsRes.data);
        setOrgs(orgsRes.data);
      } catch (err) {
        console.error("Failed to load dashboard data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <div className="page">Loading dashboard...</div>;

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: 24 }}>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>Super Admin Overview</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>Global platform metrics and system health monitoring.</p>
        </div>
      </div>

      <div className="grid-3" style={{ marginBottom: 32 }}>
        <div className="card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Total Organizations</div>
          <div className="stat-number mt-8">{stats?.organizations || 0}</div>
        </div>
        <div className="card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Total Org Admins</div>
          <div className="stat-number mt-8">{stats?.org_admins || 0}</div>
        </div>
        <div className="card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Total Interviews Scheduled</div>
          <div className="stat-number mt-8">{stats?.scheduled_interviews || 0}</div>
        </div>
      </div>

      <div className="card">
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
          <h2 style={{ fontSize: 18, margin: 0 }}>Registered Organizations</h2>
        </div>
        <div style={{ padding: 0 }}>
          {orgs.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)" }}>
              No organizations found.
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Organization Name</th>
                  <th>Created At</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {orgs.map(org => (
                  <tr key={org.id}>
                    <td className="font-semibold">{org.name}</td>
                    <td className="text-secondary">{new Date(org.created_at).toLocaleDateString()}</td>
                    <td><span className="badge badge-completed">Active</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
