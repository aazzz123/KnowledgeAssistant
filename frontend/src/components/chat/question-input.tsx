import { useState } from "react";

export function QuestionInput({
  reviewPolicy,
  onReviewPolicyChange,
  onSubmit,
}: {
  reviewPolicy: "auto" | "always" | "never";
  onReviewPolicyChange: (value: "auto" | "always" | "never") => void;
  onSubmit: (question: string) => void;
}) {
  const [value, setValue] = useState("");

  return (
    <div className="rounded-[28px] border border-black/[0.06] bg-[#fffdf9] p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="section-label">提问区</p>
          <h3 className="mt-2 text-lg font-semibold tracking-[-0.03em] text-ink">输入一个明确的问题</h3>
        </div>
        <label className="flex flex-col gap-2 text-sm text-black/58">
          <span>审核策略</span>
          <select
            className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm text-ink outline-none transition focus:border-clay/50 focus:shadow-[0_0_0_4px_rgba(191,106,52,0.12)]"
            onChange={(event) =>
              onReviewPolicyChange(event.target.value as "auto" | "always" | "never")
            }
            value={reviewPolicy}
          >
            <option value="auto">自动</option>
            <option value="always">始终审核</option>
            <option value="never">从不审核</option>
          </select>
        </label>
      </div>

      <textarea
        className="field-base mt-4 min-h-32 resize-none"
        placeholder="例如：总结这份私有文档的核心结论，并列出支撑这些结论的关键证据。"
        onChange={(event) => setValue(event.target.value)}
        value={value}
      />

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm leading-7 text-black/55">
          问题越清晰，检索证据、审核结果和导出内容通常也会越准确。
        </p>
        <button
          className="action-button-primary min-w-[132px]"
          onClick={() => {
            const question = value.trim();
            if (!question) {
              return;
            }
            onSubmit(question);
            setValue("");
          }}
          type="button"
        >
          发送问题
        </button>
      </div>
    </div>
  );
}
