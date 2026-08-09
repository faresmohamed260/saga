import React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Dashboard route error", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-3xl border border-red-500/40 bg-red-500/10 p-5 text-red-100">
          <h2 className="text-xl font-black">This dashboard section failed to render.</h2>
          <p className="mt-2 text-sm">{this.state.error?.message || String(this.state.error)}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
