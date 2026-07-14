import { useState } from "react";

import type { ChatMessage } from "@/lib/types";

export function ReviewPanel({
  message,
  onSubmit,
}: {
  message: ChatMessage | null;
  onSubmit: (approved: boolean, feedback: string) => Promise<void>;
}) {
  const [feedback, setFeedback] = useState("");

  return (
    <section className="shell-panel p-5 xl:flex-1">
      <p className="section-label">审核</p>
      <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-ink">审批面板</h2>

      {!message ? (
        <div className="mt-5 rounded-[24px] bg-[#faf6ef] p-4 text-sm leading-7 text-black/58">
          当前没有等待人工审核的答案。
        </div>
      ) : (
        <>
          <div className="mt-5 rounded-[24px] bg-[#faf6ef] p-4">
            <p className="section-label">审核原因</p>
            <p className="mt-2 text-sm leading-7 text-black/72">
              {message.reviewReason || "当前答案需要人工确认后才能正式通过。"}
            </p>
          </div>

          <textarea
            className="field-base mt-4 min-h-36 resize-none bg-white"
            onChange={(event) => setFeedback(event.target.value)}
            placeholder="补充审核意见。如果需要驳回，建议明确指出需要修改的内容。"
            value={feedback}
          />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <button
              className="action-button-primary min-w-[140px]"
              onClick={() => onSubmit(true, feedback)}
              type="button"
            >
              通过答案
            </button>
            <button
              className="action-button-secondary min-w-[140px]"
              onClick={() => onSubmit(false, feedback || "请根据审核意见修改答案后再次提交。")}
              type="button"
            >
              退回修改
            </button>
          </div>
        </>
      )}
    </section>
  );
}
