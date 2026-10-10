import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUpIcon, PageIcon, PenIcon } from "./icons";

export type Prefill = { text: string; nonce: number };

type Props = {
  disabled: boolean;
  prefill: Prefill | null;
  onSend: (content: string, hint: "essay" | "artifact" | null) => void;
};

const REQUEST = /^\s*(please\s+)?(write|make|create|draft|generate|build|turn|give me)\b/i;
const MAX_HEIGHT = 200;

/** Quick actions add their own phrasing unless the user already typed a full request. */
const withAction = (action: string, topic: string) => (REQUEST.test(topic) ? topic : `${action} on ${topic}`);

export function Composer({ disabled, prefill, onSend }: Props) {
  const [text, setText] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const topic = text.trim();

  useEffect(() => {
    if (!prefill) return;
    setText(prefill.text);
    const el = input.current;
    el?.focus();
    el?.setSelectionRange(prefill.text.length, prefill.text.length);
  }, [prefill]);

  useEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [text]);

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
      <div className="composer-chips">
        <span className="muted small">Turn a topic into:</span>
        <button type="button" className="chip-action" disabled={disabled || !topic} onClick={() => send(withAction("Write a Ship 30 essay", topic), "essay")}>
          <PenIcon size={15} /> Write a Ship 30 essay
        </button>
        <button type="button" className="chip-action" disabled={disabled || !topic} onClick={() => send(withAction("Make a one-pager", topic), "artifact")}>
          <PageIcon size={15} /> Make a one-pager
        </button>
      </div>
      <div className="composer-pill">
        <label htmlFor="composer-input" className="visually-hidden">
          Ask about Lenny's Podcast
        </label>
        <textarea
          id="composer-input"
          ref={input}
          rows={1}
          maxLength={4000}
          value={text}
          disabled={disabled}
          placeholder="Ask a question, or type a topic and pick an action…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className="send" aria-label="Send" disabled={disabled || !topic}>
          <ArrowUpIcon size={18} />
        </button>
      </div>
    </form>
  );
}
