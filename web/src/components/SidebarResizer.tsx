import { useEffect, useState, type KeyboardEvent, type PointerEvent } from "react";

export const SIDEBAR_DEFAULT = 240;
const MIN = 180;
const MAX = 420;
const STEP = 16;
const KEY = "lga.sidebarWidth";

const clamp = (w: number) => Math.min(MAX, Math.max(MIN, Math.round(w)));

export function readSidebarWidth(): number {
  try {
    const saved = Number(localStorage.getItem(KEY));
    return saved ? clamp(saved) : SIDEBAR_DEFAULT;
  } catch {
    return SIDEBAR_DEFAULT;
  }
}

function save(width: number) {
  try {
    localStorage.setItem(KEY, String(width));
  } catch {
    /* private mode: width lasts for this visit only */
  }
}

type Props = { width: number; onChange: (width: number) => void };

export function SidebarResizer({ width, onChange }: Props) {
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    document.body.classList.toggle("resizing", dragging);
  }, [dragging]);

  function set(next: number) {
    const w = clamp(next);
    onChange(w);
    save(w);
  }

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(true);
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    if (dragging) onChange(clamp(e.clientX));
  }

  function onPointerUp(e: PointerEvent<HTMLDivElement>) {
    if (!dragging) return;
    setDragging(false);
    set(e.clientX);
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, number> = { ArrowLeft: width - STEP, ArrowRight: width + STEP, Home: SIDEBAR_DEFAULT };
    if (e.key in moves) {
      e.preventDefault();
      set(moves[e.key]);
    }
  }

  return (
    <div
      className={`sidebar-resizer${dragging ? " dragging" : ""}`}
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize chat list"
      aria-valuemin={MIN}
      aria-valuemax={MAX}
      aria-valuenow={width}
      tabIndex={0}
      title="Drag to resize · double-click to reset"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => setDragging(false)}
      onDoubleClick={() => set(SIDEBAR_DEFAULT)}
      onKeyDown={onKeyDown}
    />
  );
}
