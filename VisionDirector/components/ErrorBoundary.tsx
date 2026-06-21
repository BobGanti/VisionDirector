import React from "react";

type Props = {
  children?: React.ReactNode;
};

type State = {
  hasError: boolean;
  message: string;
  stack?: string;
};

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: any): State {
    return {
      hasError: true,
      message: String(error?.message || error || "Unknown error"),
      stack: String(error?.stack || ""),
    };
  }

  componentDidCatch(error: any, info: any) {
    // Keep console logging for DevTools
    // eslint-disable-next-line no-console
    console.error("UI crashed:", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children as any;

    return (
      <div style={{ padding: 28, fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Arial" }}>
        <h1 style={{ margin: 0, fontSize: 26, fontWeight: 900 }}>UI CRASHED</h1>
        <p style={{ marginTop: 12, opacity: 0.85 }}>
          Open DevTools Console for the full error. Copy the message below if you want me to patch it precisely.
        </p>

        <div
          style={{
            marginTop: 16,
            padding: 16,
            borderRadius: 14,
            background: "rgba(0,0,0,0.35)",
            border: "1px solid rgba(255,255,255,0.08)",
            whiteSpace: "pre-wrap",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize: 13,
          }}
        >
          {this.state.message}
          {this.state.stack ? `\n\n${this.state.stack}` : ""}
        </div>

        <button
          onClick={() => window.location.reload()}
          style={{
            marginTop: 18,
            padding: "12px 18px",
            borderRadius: 12,
            border: "none",
            cursor: "pointer",
            fontWeight: 800,
          }}
        >
          Reload
        </button>
      </div>
    );
  }
}
