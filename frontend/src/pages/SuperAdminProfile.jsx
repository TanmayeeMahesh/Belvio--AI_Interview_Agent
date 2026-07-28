import { useState, useEffect } from "react";
import API from "../api";

export default function SuperAdminProfile() {
  const [profilePic, setProfilePic] = useState(null);
  const [name, setName] = useState("Super Admin");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    // Populate email from localStorage if available
    const savedEmail = localStorage.getItem("ib_email");
    if (savedEmail) {
      setEmail(savedEmail);
    }
  }, []);

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
      <h1 className="page-title">Profile Settings</h1>
      
      <div className="card" style={{ padding: 32 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 32, marginBottom: 32 }}>
          {/* Avatar Section */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
            <div 
              style={{
                width: 120, height: 120, borderRadius: "50%",
                background: "var(--bg)", border: "2px dashed var(--border)",
                display: "flex", alignItems: "center", justifyContent: "center",
                overflow: "hidden", position: "relative", cursor: "pointer"
              }}
              onClick={() => document.getElementById("avatar-upload").click()}
            >
              {profilePic ? (
                <img src={profilePic} alt="Profile" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              ) : (
                <span className="text-secondary text-sm">Upload</span>
              )}
              <div 
                style={{ 
                  position: "absolute", inset: 0, background: "rgba(0,0,0,0.5)", 
                  color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                  opacity: 0, transition: "opacity 0.2s" 
                }}
                onMouseEnter={(e) => e.currentTarget.style.opacity = 1}
                onMouseLeave={(e) => e.currentTarget.style.opacity = 0}
              >
                Change
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
            <form onSubmit={handleSave} className="gap-20">
              <div>
                <label>Full Name</label>
                <input 
                  type="text" 
                  value={name} 
                  onChange={(e) => setName(e.target.value)} 
                  required 
                />
              </div>
              <div>
                <label>Email Address</label>
                <input 
                  type="email" 
                  value={email} 
                  onChange={(e) => setEmail(e.target.value)} 
                  disabled 
                  style={{ background: "var(--bg)", cursor: "not-allowed" }}
                />
                <span className="text-xs text-secondary mt-4" style={{ display: "block" }}>
                  Email cannot be changed directly. Contact support for assistance.
                </span>
              </div>
              
              {message && <div className="text-success text-sm">{message}</div>}

              <div style={{ marginTop: 8 }}>
                <button type="submit" className="btn-primary" disabled={loading}>
                  {loading ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
