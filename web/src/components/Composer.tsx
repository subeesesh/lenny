import { useState, type KeyboardEvent } from "react";

type Props = { disabled: boolean; onSend: (content: string, hint: "essay" | "artifact" | null) => void };

export function Composer({ disabled, onSend }: Props) {
  const [text, setText] = useState("");
  const topic = text.trim();

  function send(content: string, hint: "essay" | "artifact" | null) {
    if (disabled || !topic) return;
    onSend(content, hint);
    setText("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send(topic, null);
    }
  }

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        send(topic, null);
      }}
    >
      <label htmlFor="composer-input" className="visually-hidden">
        Ask about Lenny's Podcast
      </label>
      <textarea
        id="composer-input"
        rows={2}
        maxLength={4000}
        value={text}
        disabled={disabled}
        placeholder="Ask a question, or type a topic and pick an action"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="composer-actions">
        <button type="button" className="quiet" disabled={disabled || !topic} onClick={() => send(`Write a Ship 30 essay on ${topic}`, "essay")}>
          Write a Ship 30 essay
        </button>
        <button type="button" className="quiet" disabled={disabled || !topic} onClick={() => send(`Make a one-pager on ${topic}`, "artifact")}>
          Make a one-pager
        </button>
        <button type="submit" className="primary" disabled={disabled || !topic}>
          Send
        </button>
      </div>
    </form>
  );
}
