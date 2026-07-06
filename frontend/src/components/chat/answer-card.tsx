import type { ChatMessage } from "@/lib/types";

import { AnswerDetails } from "@/components/chat/answer-details";

export function AnswerCard({ message }: { message: ChatMessage }) {
  const basisPreview = message.answerPayload?.basis?.slice(0, 3) ?? message.basisPreview ?? [];
  const badgeText =
    message.status === "streaming"
      ? "LIVE"
      : message.status === "waiting_feedback"
        ? "REVIEW"
        : message.status === "error"
          ? "ERROR"
          : "DONE";

  return (
    <article className="rounded-[30px] bg-[#fffdf9] p-5 shadow-sm ring-1 ring-black/5">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-black/45">Summary</p>
          <h2 className="mt-2 text-lg font-semibold leading-8">
            {message.conclusion || "No conclusion available."}
          </h2>
        </div>
        <span className="rounded-full bg-moss px-3 py-1 text-xs font-medium text-white">
          {badgeText}
        </span>
      </div>

      {basisPreview.length ? (
        <section className="mb-4 rounded-2xl bg-[#f6f1e8] p-4">
          <h3 className="mb-2 text-sm font-semibold">Basis</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm leading-7 text-black/75">
            {basisPreview.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <AnswerDetails message={message} />
    </article>
  );
}
