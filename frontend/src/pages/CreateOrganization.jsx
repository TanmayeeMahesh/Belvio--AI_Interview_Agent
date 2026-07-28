import { useState } from "react";
import API from "../api";

export default function CreateOrganization() {
  const [name, setName] = useState("");
  const [adminName, setAdminName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setMessage("");
    setError("");

    try {
      const { data } = await API.post("/api/admin/create-organization", {
        name,
        adminEmail: adminEmail.trim(),
        adminName: adminName.trim(),
      });
      const admin = data?.admin;
      if (adminEmail.trim()) {
        if (admin?.status === "PENDING") {
          setMessage(
            `Organization "${name}" created. Invited ${adminEmail} as Org Admin — ` +
            `they log in with this email and set their own password on first sign-in.`
          );
        } else if (admin?.status === "exists") {
          setMessage(
            `Organization "${name}" created, but ${adminEmail} already exists as a user, ` +
            `so no new admin invite was sent.`
          );
        } else {
          setMessage(`Organization "${name}" created (admin invite could not be saved).`);
        }
      } else {
        setMessage(
          `Organization "${name}" created. No admin was set — add one now, or the org ` +
          `will have nobody who can log into it.`
        );
      }
      setName("");
      setAdminName("");
      setAdminEmail("");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create organization.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 800 }}>
      <h1 className="page-title">Create Organization</h1>
      <p className="text-secondary" style={{ marginBottom: 32 }}>
        Add a new organization to the platform. An organization acts as a tenant that can have its own Org Admins and HR users.
      </p>

      <div className="card" style={{ padding: 32 }}>
        <form onSubmit={handleCreate} className="gap-20">
          <div>
            <label>Organization Name</label>
            <input
              type="text"
              placeholder="e.g. Acme Corp"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div>
            <label>Org Admin — Full Name <span className="text-secondary">(optional)</span></label>
            <input
              type="text"
              placeholder="e.g. Priya Sharma"
              value={adminName}
              onChange={(e) => setAdminName(e.target.value)}
            />
          </div>

          <div>
            <label>Org Admin — Email</label>
            <input
              type="email"
              placeholder="e.g. admin@acme.com"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
            />
            <p className="text-secondary text-sm" style={{ marginTop: 6 }}>
              The admin is invited (PENDING). They sign in with this email and set their own
              password on first login. Leave blank to add an admin later.
            </p>
          </div>

          {error && <div className="text-danger text-sm">{error}</div>}
          {message && <div className="text-success text-sm">{message}</div>}

          <div>
            <button className="btn-primary" type="submit" disabled={loading}>
              {loading ? "Creating..." : "Create Organization"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
