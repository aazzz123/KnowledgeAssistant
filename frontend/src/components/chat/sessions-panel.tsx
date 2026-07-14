"use client";

import { useState } from "react";

import type { SessionEntry } from "@/lib/types";

export function SessionsPanel({
  sessions,
  activeSessionId,
  onCreateSession,
  onSelectSession,
  onExportSession,
  onDeleteSession,
}: {
  sessions: SessionEntry[];
  activeSessionId: string;
  onCreateSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onExportSession: (sessionId: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => void;
}) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  return (
    <section className="shell-panel flex max-h-[40dvh] flex-col p-5 xl:max-h-none xl:flex-1">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="section-label">会话</p>
          <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-ink">会话记录</h2>
        </div>
        <button className="action-button-primary" onClick={onCreateSession} type="button">
          新建会话
        </button>
      </div>

      <div className="mt-5 flex-1 space-y-3 overflow-y-auto pr-1">
        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          const isMenuOpen = session.id === openMenuId;

          return (
            <article
              className={
                isActive
                  ? "rounded-[24px] border border-clay/20 bg-clay/10 p-4"
                  : "rounded-[24px] border border-black/[0.06] bg-white/60 p-4 transition hover:bg-white/80"
              }
              key={session.id}
            >
              <div className="flex gap-3">
                <button
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onSelectSession(session.id)}
                  type="button"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={
                        isActive
                          ? "h-2.5 w-2.5 rounded-full bg-clay"
                          : "h-2.5 w-2.5 rounded-full bg-black/15"
                      }
                    />
                    <p className="truncate text-sm font-semibold text-ink">{session.title}</p>
                  </div>
                  <p className="mt-2 text-xs leading-6 text-black/52">
                    {new Date(session.createdAt).toLocaleString()}
                  </p>
                </button>

                <div className="relative shrink-0">
                  <button
                    aria-label="打开会话菜单"
                    className="rounded-full border border-black/[0.08] bg-white px-3 py-1.5 text-xs font-medium text-black/65 transition hover:bg-black/[0.03]"
                    onClick={() =>
                      setOpenMenuId((current) => (current === session.id ? null : session.id))
                    }
                    type="button"
                  >
                    管理
                  </button>

                  {isMenuOpen ? (
                    <div className="absolute right-0 top-10 z-10 min-w-40 rounded-[20px] border border-black/[0.08] bg-white p-2 shadow-2xl shadow-black/[0.10]">
                      <button
                        className="w-full rounded-2xl px-3 py-2 text-left text-sm text-ink transition hover:bg-[#f8f3ea]"
                        onClick={async () => {
                          setOpenMenuId(null);
                          await onExportSession(session.id);
                        }}
                        type="button"
                      >
                        导出 PDF
                      </button>
                      <button
                        className="mt-1 w-full rounded-2xl px-3 py-2 text-left text-sm text-[#9d402d] transition hover:bg-[#fdf0ea]"
                        onClick={() => {
                          setOpenMenuId(null);
                          onDeleteSession(session.id);
                        }}
                        type="button"
                      >
                        删除会话
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
