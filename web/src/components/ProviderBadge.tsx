import { useEffect, useRef, useState } from "react";
import type { Config } from "../api";

type Props = { config: Config | null; disabled: boolean; onSelect: (provider: string) => void };

export const shortModel = (model: string) => model.replace(/-\d{4}-q\w+$/i, "");

export function ProviderBadge({ config, disabled, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  if (!config) return <span className="badge muted">Loading…</span>;
  const active = config.providers.find((p) => p.name === config.active.provider);
  const icon = config.active.provider === "ollama" ? "🖥" : "☁";
  const label = `${active?.label ?? config.active.provider} · ${shortModel(config.active.model)}`;

  return (
    <div className="badge-wrap" ref={ref}>
      <button
        type="button"
        className="badge"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Model: ${label}. Change model`}
        disabled={disabled}
        onClick={() => setOpen(!open)}
      >
        <span aria-hidden="true">{icon}</span> {label} <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul className="menu" role="menu">
          {config.providers.map((p) => (
            <li key={p.name} role="none">
              <button
                type="button"
                role="menuitemradio"
                aria-checked={p.name === config.active.provider}
                disabled={!p.available}
                onClick={() => {
                  setOpen(false);
                  onSelect(p.name);
                }}
              >
                <span>
                  {p.label} · {shortModel(p.model)}
                </span>
                <span className="muted small">{p.available ? "available" : p.reason}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
