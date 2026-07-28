import { useEffect, useState } from "react";
import API from "../api";

export default function Organizations() {
  const [orgs, setOrgs] = useState([]);
  const [name, setName] = useState("");

  useEffect(() => {
    loadOrganizations();
  }, []);

  async function loadOrganizations() {
    const { data } = await API.get("/api/admin/organizations");
    setOrgs(data);
  }

  async function createOrganization() {
    await API.post("/api/admin/create-organization", {
      name,
    });

    setName("");
    loadOrganizations();
  }

  async function deleteOrganization(id) {
    await API.delete(`/api/admin/organizations/${id}`);
    loadOrganizations();
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>Organizations</h1>

      <div style={{ marginBottom: 20 }}>
        <input
          placeholder="Organization Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <button onClick={createOrganization}>Create Organization</button>
      </div>

      {orgs.map((org) => (
        <div
          key={org.id}
          style={{
            border: "1px solid #ddd",
            padding: 12,
            marginBottom: 10,
          }}
        >
          <strong>{org.name}</strong>

          <button
            style={{ marginLeft: 20 }}
            onClick={() => deleteOrganization(org.id)}
          >
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}
