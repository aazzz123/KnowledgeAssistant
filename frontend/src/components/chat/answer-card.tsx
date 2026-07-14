import type { ChatMessage } from "@/lib/types";

import { AnswerDetails } from "@/components/chat/answer-details";

const STATUS_STYLES: Record<string, string> = {
  streaming: "bg-clay/10 text-clay",
  waiting_feedback: "bg-[#f7ede5] text-[#9d4d23]",
  error: "bg-[#fff0eb] text-[#b0432c]",
  completed: "bg-[#f5efe5] text-ink",
};

const STATUS_LABELS: Record<string, string> = {
  streaming: "生成中",
  waiting_feedback: "待审核",
  error: "异常",
  completed: "完成",
};

export function AnswerCard({ message }: { message: ChatMessage }) {
  const basisPreview = message.answerPayload?.basis?.slice(0, 3) ?? message.basisPreview ?? [];
  const statusKey = message.status ?? "completed";

  return (
    <article className="rounded-[30px] border border-black/[0.06] bg-[#fffdf9] p-5 shadow-[0_24px_80px_rgba(31,25,17,0.06)] sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-3xl">
          <p className="section-label">最新答案</p>
          <h2 className="mt-3 text-xl font-semibold leading-9 tracking-[-0.04em] text-ink sm:text-[1.7rem]">
            {message.conclusion || "暂无结论。"}
          </h2>
        </div>
        <span
          className={`status-pill self-start ${STATUS_STYLES[statusKey] ?? STATUS_STYLES.completed}`}
        >
          {STATUS_LABELS[statusKey] ?? STATUS_LABELS.completed}
        </span>
      </div>

      {basisPreview.length ? (
        <section className="mt-5 rounded-[24px] bg-[#f8f3ea] p-4 sm:p-5">
          <p className="section-label">依据摘要</p>
          <ul className="mt-3 space-y-2 text-sm leading-7 text-black/72">
            {basisPreview.map((item) => (
              <li className="rounded-2xl bg-white/72 px-4 py-3" key={item}>
                {item}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="mt-5">
        <AnswerDetails message={message} />
      </div>
    </article>
  );
}
