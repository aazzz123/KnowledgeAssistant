import type { EvidenceItem } from "@/lib/types";

export function EvidenceDrawer({ evidence }: { evidence: EvidenceItem[] }) {
  return (
    <section className="shell-panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="section-label">证据</p>
          <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-ink">检索面板</h2>
        </div>
        <span className="rounded-full border border-black/[0.08] px-3 py-1 text-sm text-black/58">
          {evidence.length} 条
        </span>
      </div>

      <div className="mt-5 space-y-3">
        {evidence.length === 0 ? (
          <div className="rounded-[24px] bg-[#faf6ef] p-4 text-sm leading-7 text-black/58">
            助手完成检索后，相关证据会显示在这里。
          </div>
        ) : (
          evidence.map((item) => (
            <details
              className="rounded-[24px] border border-black/[0.06] bg-white/72 p-4"
              key={item.evidence_id}
            >
              <summary className="cursor-pointer list-none">
                <p className="text-sm font-semibold text-ink">
                  {item.metadata.title || "未命名文档"}
                </p>
                <p className="mt-1 text-xs leading-6 text-black/50">
                  第 {item.metadata.page || "?"} 页，章节 {item.metadata.section || "未标注"}
                </p>
              </summary>

              <div className="mt-4 space-y-3 text-sm leading-7 text-black/68">
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="rounded-2xl bg-[#faf6ef] px-3 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-black/42">
                      文档编号
                    </p>
                    <p className="mt-1 break-all">{item.metadata.document_id || "暂无"}</p>
                  </div>
                  <div className="rounded-2xl bg-[#faf6ef] px-3 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-black/42">
                      分数
                    </p>
                    <p className="mt-1">
                      rerank {item.rerank_score} / dense {item.dense_score} / bm25 {item.bm25_score}
                    </p>
                  </div>
                </div>
                <div className="rounded-[20px] bg-[#faf6ef] px-4 py-4">
                  <p>{item.text}</p>
                </div>
              </div>
            </details>
          ))
        )}
      </div>
    </section>
  );
}
