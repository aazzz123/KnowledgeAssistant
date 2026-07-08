import type { ChatMessage } from "@/lib/types";

export function AnswerDetails({ message }: { message: ChatMessage }) {
  // 详情区只负责展开结构化字段，避免主卡片承担太多信息密度。
  const payload = message.answerPayload;

  return (
    <details className="rounded-2xl bg-[#f6f1e8] p-4">
      <summary className="cursor-pointer list-none text-sm font-medium">Show details</summary>
      <div className="mt-4 space-y-4 text-sm leading-7 text-black/75">
        <section>
          <h3 className="mb-1 font-semibold">Basis</h3>
          <ul className="list-disc space-y-1 pl-5">
            {(payload?.basis ?? []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="mb-1 font-semibold">Citations</h3>
          <ul className="list-disc space-y-1 pl-5">
            {(payload?.citations ?? []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="mb-1 font-semibold">Evidence gaps</h3>
          <ul className="list-disc space-y-1 pl-5">
            {(payload?.evidence_gaps ?? []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="mb-1 font-semibold">Review note</h3>
          <p>{payload?.review_note || message.reviewReason || "No review note available."}</p>
        </section>
        {message.exportPath ? (
          <section>
            <h3 className="mb-1 font-semibold">Export path</h3>
            <p className="break-all">{message.exportPath}</p>
          </section>
        ) : null}
      </div>
    </details>
  );
}
