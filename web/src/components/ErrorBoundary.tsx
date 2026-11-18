"use client";

import { Component, type ReactNode } from "react";

type Props = { children: ReactNode; label?: string };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    if (prev.children !== this.props.children && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-8 text-center text-sm text-[var(--danger)]">
          <p className="font-semibold">
            Falha ao renderizar {this.props.label || "esta aba"}.
          </p>
          <p className="mt-1 text-[var(--muted)]">{this.state.error.message}</p>
          <button
            type="button"
            className="mt-3 rounded-lg bg-[var(--p1)] px-3 py-1.5 text-white"
            onClick={() => this.setState({ error: null })}
          >
            Tentar de novo
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
