import type { SessionMemoryResponse } from "@/lib/types";

export function MemoryDrawer({ memory }: { memory: SessionMemoryResponse | null }) {
  // 这里展示的是会话摘要视图，不是完整记忆原文，重点是帮用户快速找上下文。
  return (
    <section className="h-full rounded-[28px] bg-white p-5 shadow-sm ring-1 ring-black/5">
      <h2 className="text-base font-semibold">会话记忆</h2>
      <div className="mt-4 space-y-4 text-sm leading-7 text-black/65">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-black/40">Current Topic</p>
          <p className="mt-1">{memory?.current_topic || "暂无主题"}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-black/40">Recent Questions</p>
          {memory?.recent_questions?.length ? (
            <ul className="mt-1 list-disc pl-5">
              {memory.recent_questions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1">暂无问题记录</p>
          )}
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-black/40">Confirmed Answers</p>
          {memory?.confirmed_answers?.length ? (
            <ul className="mt-1 list-disc pl-5">
              {memory.confirmed_answers.map((answer) => (
                <li key={answer}>{answer}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1">暂无确认答案</p>
          )}
        </div>
      </div>
    </section>
  );
}
