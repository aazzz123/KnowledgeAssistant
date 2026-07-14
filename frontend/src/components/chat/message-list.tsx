import type { ChatMessage } from "@/lib/types";

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  return (
    <div className="space-y-4">
      {messages.map((message) => {
        const isUser = message.role === "user";
        const content =
          message.question || message.conclusion || (message.status === "streaming" ? "正在生成回答..." : "");

        return (
          <div className={isUser ? "flex justify-end" : "flex justify-start"} key={message.id}>
            <article
              className={
                isUser
                  ? "max-w-[85%] rounded-[26px] rounded-br-[10px] bg-ink px-5 py-4 text-white shadow-lg shadow-black/[0.08]"
                  : "max-w-[88%] rounded-[26px] rounded-bl-[10px] border border-black/[0.06] bg-white/72 px-5 py-4 text-ink"
              }
            >
              <div className="mb-2 flex items-center gap-2">
                <span
                  className={
                    isUser ? "h-2 w-2 rounded-full bg-white/70" : "h-2 w-2 rounded-full bg-clay"
                  }
                />
                <p
                  className={
                    isUser
                      ? "text-[11px] font-semibold uppercase tracking-[0.16em] text-white/72"
                      : "text-[11px] font-semibold uppercase tracking-[0.16em] text-black/45"
                  }
                >
                  {isUser ? "问题" : "助手"}
                </p>
              </div>
              <p
                className={
                  isUser ? "text-sm leading-7 text-white/95" : "text-sm leading-7 text-black/76"
                }
              >
                {content}
              </p>
            </article>
          </div>
        );
      })}
    </div>
  );
}
