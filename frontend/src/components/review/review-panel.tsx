import { useState } from "react";

import type { ChatMessage } from "@/lib/types";

export function ReviewPanel({
  message,
  onSubmit
}: {
  message: ChatMessage | null;
  onSubmit: (approved: boolean, feedback: string) => Promise<void>;
}) {
  const [feedback, setFeedback] = useState("");

  return (
    <section className="rounded-[28px] bg-white p-5 shadow-sm ring-1 ring-black/5">
      <h2 className="text-base font-semibold">审核面板</h2>
      {!message ? (
        <div className="mt-4 rounded-2xl bg-[#f8f5ee] p-4 text-sm text-black/65">
          当前没有待审核内容。
        </div>
      ) : (
        <>
          <p className="mt-2 text-sm leading-7 text-black/60">
            {message.reviewReason || "当前回答需要人工审核，请决定是否通过。"}
          </p>
          <textarea
            className="mt-4 min-h-28 w-full resize-none rounded-2xl border border-black/10 bg-[#fcfaf4] px-4 py-3 text-sm outline-none"
            onChange={(event) => setFeedback(event.target.value)}
            placeholder="填写审核意见。若驳回，建议说明需要修改的内容。"
            value={feedback}
          />
          <div className="mt-4 flex gap-3">
            <button
              className="rounded-full bg-moss px-4 py-2 text-sm font-medium text-white"
              onClick={() => onSubmit(true, feedback)}
              type="button"
            >
              通过
            </button>
            <button
              className="rounded-full bg-clay px-4 py-2 text-sm font-medium text-white"
              onClick={() => onSubmit(false, feedback || "请根据审核意见修改答案。")}
              type="button"
            >
              驳回并修改
            </button>
          </div>
        </>
      )}
    </section>
  );
}
