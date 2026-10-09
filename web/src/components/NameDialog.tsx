import { useEffect, useRef, useState } from "react";

export function NameDialog({ onSave }: { onSave: (name: string) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState("");

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  return (
    <dialog ref={ref} className="name-dialog" aria-labelledby="name-title" onCancel={(e) => e.preventDefault()}>
      <form
        method="dialog"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onSave(name.trim());
        }}
      >
        <h2 id="name-title">What should we call you?</h2>
        <p className="muted">Your name is saved in this browser and attached to your chats.</p>
        <label htmlFor="display-name">Display name</label>
        <input id="display-name" maxLength={60} required autoFocus value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="primary">
          Continue
        </button>
      </form>
    </dialog>
  );
}
