import { useEffect, useRef } from "react";
import type { SessionSummary } from "../api";
import { TrashIcon } from "./icons";
import { displayTitle } from "./Sidebar";

type Props = { session: SessionSummary; onConfirm: () => void; onCancel: () => void };

export function DeleteDialog({ session, onConfirm, onCancel }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  return (
    <dialog ref={ref} className="name-dialog delete-dialog" aria-labelledby="delete-title" aria-describedby="delete-text" onCancel={onCancel}>
      <span className="delete-icon" aria-hidden="true">
        <TrashIcon size={20} />
      </span>
      <h2 id="delete-title">Delete this chat?</h2>
      <p className="delete-name">{displayTitle(session.title).text}</p>
      <p id="delete-text" className="muted">
        Its messages and documents will be removed. This can't be undone.
      </p>
      <div className="dialog-actions">
        <button type="button" autoFocus onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="danger" onClick={onConfirm}>
          Delete chat
        </button>
      </div>
    </dialog>
  );
}
