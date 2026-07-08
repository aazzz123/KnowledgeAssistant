import type { EvidenceItem } from "@/lib/types";

export function EvidenceDrawer({ evidence }: { evidence: EvidenceItem[] }) {
  // 证据面板主要给追溯和排查用，所以把分数和元数据都保留下来。
  return (
    <section className="rounded-[28px] bg-white p-5 shadow-sm ring-1 ring-black/5">
      <h2 className="text-base font-semibold">证据面板</h2>
      <div className="mt-4 space-y-3 text-sm">
        {evidence.length === 0 ? (
          <div className="rounded-2xl bg-[#f8f5ee] p-4 text-black/65">
            当前还没有检索证据。
          </div>
        ) : (
          evidence.map((item) => (
            <details className="rounded-2xl bg-[#f8f5ee] p-4" key={item.evidence_id}>
              <summary className="cursor-pointer list-none font-medium">
                {item.metadata.title || "未命名文档"} / 第 {item.metadata.page || "?"} 页
              </summary>
              <div className="mt-2 space-y-2 text-black/65">
                <p>section: {item.metadata.section || "未标注"}</p>
                <p>document_id: {item.metadata.document_id || "未标注"}</p>
                <p>
                  scores: rerank {item.rerank_score} / dense {item.dense_score} / bm25{" "}
                  {item.bm25_score}
                </p>
                <p className="leading-7">{item.text}</p>
              </div>
            </details>
          ))
        )}
      </div>
    </section>
  );
}
