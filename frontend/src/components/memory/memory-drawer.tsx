import type { SessionMemoryResponse } from "@/lib/types";

export function MemoryDrawer({ memory }: { memory: SessionMemoryResponse | null }) {
  return (
    <section className="shell-panel p-5 xl:flex-1">
      <p className="section-label">记忆</p>
      <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-ink">会话上下文</h2>

      <div className="mt-5 space-y-4 text-sm leading-7">
        <MemoryBlock title="当前主题" value={memory?.current_topic || "暂无主题"} />
        <MemoryList
          title="最近问题"
          items={memory?.recent_questions ?? []}
          emptyLabel="暂无最近问题记录。"
        />
        <MemoryList
          title="已确认答案"
          items={memory?.confirmed_answers ?? []}
          emptyLabel="暂无已确认答案。"
        />
      </div>
    </section>
  );
}

function MemoryBlock({ title, value }: { title: string; value: string }) {
  return (
    <section className="rounded-[24px] bg-[#faf6ef] p-4">
      <p className="section-label">{title}</p>
      <p className="mt-2 text-sm leading-7 text-black/72">{value}</p>
    </section>
  );
}

function MemoryList({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: string[];
  emptyLabel: string;
}) {
  return (
    <section className="rounded-[24px] bg-[#faf6ef] p-4">
      <p className="section-label">{title}</p>
      {items.length ? (
        <div className="mt-3 space-y-2">
          {items.map((item) => (
            <div
              className="rounded-2xl bg-white/72 px-4 py-3 text-sm leading-7 text-black/72"
              key={item}
            >
              {item}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-7 text-black/55">{emptyLabel}</p>
      )}
    </section>
  );
}
