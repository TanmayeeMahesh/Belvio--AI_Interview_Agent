import React from "react";

export default function DashboardPreview() {
  return (
    <section style={{ padding: "100px 24px", position: "relative" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto", textAlign: "center" }}>
        <h2 style={{ fontSize: 36, marginBottom: 24, color: "#fff" }}>
          Everything in One Place
        </h2>
        <p
          style={{
            color: "rgba(255,255,255,0.6)",
            marginBottom: 64,
            fontSize: 18,
          }}
        >
          Manage your pipeline, view candidate analytics, and read deep
          evaluation reports.
        </p>

        <div
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 24,
            padding: 32,
            boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)",
            display: "flex",
            gap: 24,
            flexWrap: "wrap",
            justifyContent: "center",
            backdropFilter: "blur(12px)",
          }}
        >
          {/* Mock Dashboard Cards */}
          <div
            style={{
              background: "rgba(15,23,42,0.8)",
              border: "1px solid rgba(255,255,255,0.05)",
              borderRadius: 16,
              padding: 24,
              flex: "1 1 200px",
              textAlign: "left",
              backdropFilter: "blur(12px)",
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "var(--accent)",
                textTransform: "uppercase",
                fontWeight: 600,
                letterSpacing: "0.05em",
                marginBottom: 8,
              }}
            >
              HR Dashboard
            </div>
            <div
              style={{
                height: 8,
                background: "rgba(255,255,255,0.1)",
                borderRadius: 4,
                marginBottom: 12,
                width: "60%",
              }}
            ></div>
            <div
              style={{
                height: 8,
                background: "rgba(255,255,255,0.1)",
                borderRadius: 4,
                marginBottom: 12,
                width: "80%",
              }}
            ></div>
            <div
              style={{
                height: 8,
                background: "rgba(255,255,255,0.1)",
                borderRadius: 4,
                width: "40%",
              }}
            ></div>
          </div>

          <div
            style={{
              background: "rgba(15,23,42,0.8)",
              border: "1px solid rgba(255,255,255,0.05)",
              borderRadius: 16,
              padding: 24,
              flex: "1 1 200px",
              textAlign: "left",
              backdropFilter: "blur(12px)",
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "var(--success)",
                textTransform: "uppercase",
                fontWeight: 600,
                letterSpacing: "0.05em",
                marginBottom: 8,
              }}
            >
              AI Score: 92/100
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <div
                style={{
                  height: 40,
                  width: 40,
                  borderRadius: 8,
                  background: "rgba(34,197,94,0.2)",
                }}
              ></div>
              <div
                style={{
                  flex: 1,
                  height: 40,
                  borderRadius: 8,
                  background: "rgba(255,255,255,0.05)",
                  backdropFilter: "blur(12px)",
                }}
              ></div>
            </div>
            <div
              style={{
                height: 8,
                background: "rgba(255,255,255,0.1)",
                borderRadius: 4,
                width: "90%",
              }}
            ></div>
          </div>

          <div
            style={{
              background: "rgba(15,23,42,0.8)",
              border: "1px solid rgba(255,255,255,0.05)",
              borderRadius: 16,
              padding: 24,
              flex: "1 1 200px",
              textAlign: "left",
              backdropFilter: "blur(12px)",
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "var(--warning)",
                textTransform: "uppercase",
                fontWeight: 600,
                letterSpacing: "0.05em",
                marginBottom: 8,
              }}
            >
              Evaluation Report
            </div>
            <div
              style={{
                height: 60,
                background: "rgba(255,255,255,0.05)",
                borderRadius: 8,
                marginBottom: 12,
                backdropFilter: "blur(12px)",
              }}
            ></div>
            <div
              style={{
                height: 8,
                background: "rgba(255,255,255,0.1)",
                borderRadius: 4,
                width: "50%",
              }}
            ></div>
          </div>
        </div>
      </div>
    </section>
  );
}
