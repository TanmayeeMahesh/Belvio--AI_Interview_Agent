import { useEffect, useState } from "react";
import API from "../api";

export default function OrgSettings() {
  const [template, setTemplate] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    try {
      const { data } = await API.get("/api/org-admin/settings");
      if (data.email_template) {
        setTemplate(data.email_template);
      } else {
        setTemplate("");
      }
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  }

  async function saveSettings(e) {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      await API.put("/api/org-admin/settings", { email_template: template });
      setMessage("Settings saved successfully.");
      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      console.error(err);
      setMessage("Failed to save settings.");
    }
    setSaving(false);
  }

  if (loading) return <div className="page">Loading settings...</div>;

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: 32 }}>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>Organization Settings</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>Manage your organization's profile and core preferences.</p>
        </div>
      </div>

      <div className="card" style={{ padding: 32, maxWidth: 800 }}>
        <h2 style={{ marginTop: 0, marginBottom: 16 }}>Candidate Invitation Email</h2>
        <p className="text-secondary" style={{ marginBottom: 24 }}>
          Customize the email draft sent to candidates when an interview is scheduled. 
          Leave this blank to use the Belvio default template.
        </p>

        <div style={{ marginBottom: 24, padding: 16, background: "rgba(255,255,255,0.05)", borderRadius: 8 }}>
          <h3 style={{ fontSize: 14, margin: "0 0 12px 0", color: "var(--text-secondary)" }}>Available Placeholders:</h3>
          <ul style={{ margin: 0, paddingLeft: 20, color: "var(--text-secondary)", fontSize: 14, display: "flex", flexDirection: "column", gap: 8 }}>
            <li><code>{"{candidate_name}"}</code> — The candidate's full name</li>
            <li><code>{"{role}"}</code> — The job role they are interviewing for</li>
            <li><code>{"{when}"}</code> — The scheduled date and time</li>
            <li><code>{"{meeting_url}"}</code> — The unique Google Meet join link</li>
            <li><code>{"{organization_name}"}</code> — Your organization's name</li>
          </ul>
        </div>

        <form onSubmit={saveSettings} style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div>
            <label style={{ display: "block", marginBottom: 8, fontWeight: 500 }}>Email Body</label>
            <textarea
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              placeholder="Hello {candidate_name}, you are invited..."
              style={{
                width: "100%",
                height: 250,
                background: "rgba(255, 255, 255, 0.05)",
                color: "var(--text)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: 8,
                padding: 16,
                fontFamily: "inherit",
                fontSize: 14,
                resize: "vertical"
              }}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Save Template"}
            </button>
            {message && (
              <span style={{ color: message.includes("Failed") ? "var(--danger)" : "var(--success)", fontSize: 14 }}>
                {message}
              </span>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
