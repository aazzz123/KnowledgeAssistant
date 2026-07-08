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
  // Keep the draft locally so the parent only receives a clean submitted question.
  const [value, setValue] = useState("");

  return (
    <div className="rounded-[28px] bg-[#fcfaf4] p-4 ring-1 ring-black/5">
      <div className="mb-3 flex items-center justify-between">
        <label className="text-sm font-medium">Question</label>
        <select
          className="rounded-full border border-black/10 bg-white px-3 py-1 text-sm"
          onChange={(event) =>
            onReviewPolicyChange(event.target.value as "auto" | "always" | "never")
          }
          value={reviewPolicy}
        >
          <option value="auto">auto</option>
          <option value="always">always</option>
          <option value="never">never</option>
        </select>
      </div>
      <textarea
        className="min-h-28 w-full resize-none rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm outline-none"
        placeholder="For example: summarize the key points in this private document and cite the supporting evidence."
        onChange={(event) => setValue(event.target.value)}
        value={value}
      />
      <div className="mt-4 flex justify-end">
        <button
          className="rounded-full bg-clay px-5 py-2 text-sm font-medium text-white transition hover:opacity-90"
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
          Send
        </button>
      </div>
    </div>
  );
}
