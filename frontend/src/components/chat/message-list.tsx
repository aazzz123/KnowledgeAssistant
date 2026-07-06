import type { ChatMessage } from "@/lib/types";

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  return (
    <div className="space-y-3">
      {messages.map((message) => (
        <div
          key={message.id}
          className={
            message.role === "user"
              ? "ml-auto max-w-[80%] rounded-3xl bg-ink px-5 py-4 text-paper"
              : "max-w-[85%] rounded-3xl bg-[#f4ead7] px-5 py-4 text-ink"
          }
        >
          <p className="mb-1 text-xs uppercase tracking-[0.2em] text-black/45">
            {message.role === "user" ? "User" : "Assistant"}
          </p>
          <p className="text-sm leading-7">
            {message.question ||
              message.conclusion ||
              (message.status === "streaming" ? "Generating answer..." : "")}
          </p>
        </div>
      ))}
    </div>
  );
}
