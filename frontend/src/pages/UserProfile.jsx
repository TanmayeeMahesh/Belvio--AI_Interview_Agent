import { useState, useEffect } from "react";
import API from "../api";

export default function UserProfile({ role, initialEmail }) {
  const [profilePic, setProfilePic] = useState(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    // Populate email from props or localStorage if available
    const savedEmail = initialEmail || localStorage.getItem("ib_email");
    if (savedEmail) {
      setEmail(savedEmail);
    }
    
    // Set a default name based on role if no name is available
    if (role === "SUPER_ADMIN") setName("Super Admin");
    else if (role === "ORG_ADMIN") setName("Organization Admin");
    else if (role === "HR") setName("HR Recruiter");
  }, [role, initialEmail]);

  const handleImageChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setProfilePic(URL.createObjectURL(e.target.files[0]));
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    
    // Mock save delay
    setTimeout(() => {
      setMessage("Profile updated successfully!");
      setLoading(false);
    }, 800);
  };

  return (
    <div className="page" style={{ maxWidth: 800 }}>
      <div className="flex-between" style={{ marginBottom: 32 }}>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>My Profile</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>Manage your personal account settings and profile picture.</p>
        </div>
      </div>
      
      <div className="card" style={{ padding: 32 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 40 }}>
          {/* Avatar Section */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
            <div 
              style={{
                width: 140, height: 140, borderRadius: "50%",
                background: "var(--surface)", border: "2px dashed var(--border)",
                display: "flex", alignItems: "center", justifyContent: "center",
                overflow: "hidden", position: "relative", cursor: "pointer",
                boxShadow: "var(--shadow)"
              }}
              onClick={() => document.getElementById("avatar-upload").click()}
            >
              {profilePic ? (
                <img src={profilePic} alt="Profile" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              ) : (
                <span style={{ fontSize: 40, color: "var(--primary)", fontWeight: 300 }}>{name ? name.charAt(0).toUpperCase() : "+"}</span>
              )}
              <div 
                style={{ 
                  position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)", 
                  color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                  opacity: 0, transition: "opacity 0.2s", fontSize: 14, fontWeight: 500 
                }}
                onMouseEnter={(e) => e.currentTarget.style.opacity = 1}
                onMouseLeave={(e) => e.currentTarget.style.opacity = 0}
              >
                Change Avatar
              </div>
            </div>
            <input 
              type="file" 
              id="avatar-upload" 
              accept="image/*" 
              style={{ display: "none" }} 
              onChange={handleImageChange}
            />
          </div>

          {/* Form Section */}
          <div style={{ flex: 1 }}>
            <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              <div>
                <label style={{ display: "block", marginBottom: 8, fontWeight: 500, fontSize: 14 }}>Full Name</label>
                <input 
                  type="text" 
                  value={name} 
                  onChange={(e) => setName(e.target.value)} 
                  required 
                  style={{ width: "100%", padding: "12px 16px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }}
                />
              </div>
              
              <div>
                <label style={{ display: "block", marginBottom: 8, fontWeight: 500, fontSize: 14 }}>Email Address</label>
                <input 
                  type="email" 
                  value={email} 
                  onChange={(e) => setEmail(e.target.value)} 
                  disabled 
                  style={{ width: "100%", padding: "12px 16px", borderRadius: 8, border: "1px solid var(--border)", background: "rgba(0,0,0,0.02)", color: "var(--text-secondary)", cursor: "not-allowed" }}
                />
                <span className="text-secondary" style={{ display: "block", fontSize: 12, marginTop: 6 }}>
                  Email cannot be changed directly. Contact support for assistance.
                </span>
              </div>
              
              <div>
                <label style={{ display: "block", marginBottom: 8, fontWeight: 500, fontSize: 14 }}>Role</label>
                <div style={{ padding: "12px 16px", borderRadius: 8, border: "1px solid var(--border)", background: "rgba(0,0,0,0.02)", color: "var(--text-secondary)", fontWeight: 500 }}>
                  {role?.replace("_", " ")}
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 8 }}>
                <button type="submit" className="btn-primary" disabled={loading} style={{ padding: "12px 24px" }}>
                  {loading ? "Saving..." : "Save Changes"}
                </button>
                {message && <div style={{ color: "var(--success)", fontSize: 14, fontWeight: 500 }}>{message}</div>}
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
