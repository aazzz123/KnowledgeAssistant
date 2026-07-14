import type { ChatMessage } from "@/lib/types";

export function AnswerDetails({ message }: { message: ChatMessage }) {
  const payload = message.answerPayload;
  const sections = [
    { title: "依据", items: payload?.basis ?? [] },
    { title: "引用", items: payload?.citations ?? [] },
    { title: "证据缺口", items: payload?.evidence_gaps ?? [] },
  ];

  return (
    <details className="rounded-[24px] border border-black/[0.06] bg-white/70 p-4 sm:p-5">
      <summary className="cursor-pointer list-none text-sm font-semibold text-ink">
        结构化详情
      </summary>
      <div className="mt-4 space-y-4">
        {sections.map((section) => (
          <section className="rounded-[20px] bg-[#faf6ef] p-4" key={section.title}>
            <h3 className="text-sm font-semibold text-ink">{section.title}</h3>
            {section.items.length ? (
              <ul className="mt-3 space-y-2 text-sm leading-7 text-black/70">
                {section.items.map((item) => (
                  <li className="rounded-2xl bg-white/75 px-4 py-3" key={item}>
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm leading-7 text-black/55">暂无数据。</p>
            )}
          </section>
        ))}

        <section className="rounded-[20px] bg-[#faf6ef] p-4">
          <h3 className="text-sm font-semibold text-ink">审核说明</h3>
          <p className="mt-3 text-sm leading-7 text-black/68">
            {payload?.review_note || message.reviewReason || "暂无审核说明。"}
          </p>
        </section>

        {message.exportPath ? (
          <section className="rounded-[20px] bg-[#faf6ef] p-4">
            <h3 className="text-sm font-semibold text-ink">导出路径</h3>
            <p className="mt-3 break-all text-sm leading-7 text-black/68">{message.exportPath}</p>
          </section>
        ) : null}
      </div>
    </details>
  );
}
