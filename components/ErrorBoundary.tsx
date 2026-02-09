import React from "react";

type Props = { children: React.ReactNode };
type State = { hasError: boolean; message: string; stack?: string };

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(err: any) {
    return { hasError: true, message: String(err?.message || err || "Unknown error") };
  }

  componentDidCatch(err: any, info: any) {
    // Log so you can see it in DevTools
    console.error("[VisionDirector] UI crashed:", err, info);
    this.setState({ stack: String(info?.componentStack || "") });
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div style={{ minHeight: "100vh", background: "#020202", color: "#fff", padding: 24 }}>
        <h1 style={{ fontWeight: 900, letterSpacing: 1 }}>UI CRASHED</h1>
        <p style={{ opacity: 0.8, marginTop: 8 }}>
          Open DevTools Console for the full error. Copy the message below if you want me to patch it precisely.
        </p>
        <pre style={{
          marginTop: 16, padding: 16, background: "#111", borderRadius: 12,
          whiteSpace: "pre-wrap", wordBreak: "break-word", border: "1px solid rgba(255,255,255,0.1)"
        }}>
{this.state.message}
{"\n\n"}
{this.state.stack || ""}
        </pre>

        <button
          onClick={() => window.location.reload()}
          style={{
            marginTop: 16, padding: "10px 16px", borderRadius: 10,
            background: "#fff", color: "#000", fontWeight: 800, border: "none", cursor: "pointer"
          }}
        >
          Reload
        </button>
      </div>
    );
  }
}
