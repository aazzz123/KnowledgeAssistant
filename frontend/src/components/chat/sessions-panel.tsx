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
  // 这里只维护哪一个菜单打开，不把菜单状态抬到父组件，省得会话切换时联动太多。
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  return (
    <section className="rounded-[28px] bg-white/80 p-5 shadow-sm ring-1 ring-black/5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Sessions</h2>
        <button
          className="rounded-full bg-clay px-3 py-1 text-xs font-medium text-white"
          onClick={onCreateSession}
          type="button"
        >
          New
        </button>
      </div>
      <div className="mt-4 space-y-2">
        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          const isMenuOpen = session.id === openMenuId;

          return (
            <div
              className={
                isActive
                  ? "rounded-2xl bg-ink px-3 py-3 text-paper"
                  : "rounded-2xl bg-[#f8f5ee] px-3 py-3 text-ink"
              }
              key={session.id}
            >
              <div className="flex items-start gap-2">
                <button
                  className="flex-1 text-left"
                  onClick={() => onSelectSession(session.id)}
                  type="button"
                >
                  <p className="truncate font-medium">{session.title}</p>
                  <p className="mt-1 text-xs opacity-70">
                    {new Date(session.createdAt).toLocaleString()}
                  </p>
                </button>
                <div className="relative">
                  {/* 三点菜单里只放轻操作，避免左侧会话区变得太重。 */}
                  <button
                    className={
                      isActive
                        ? "rounded-full px-2 py-1 text-xs text-paper/80 hover:bg-white/10"
                        : "rounded-full px-2 py-1 text-xs text-ink/70 hover:bg-black/5"
                    }
                    onClick={() =>
                      setOpenMenuId((current) => (current === session.id ? null : session.id))
                    }
                    type="button"
                  >
                    ...
                  </button>
                  {isMenuOpen ? (
                    <div className="absolute right-0 top-8 z-10 min-w-36 rounded-2xl bg-white p-2 text-sm text-ink shadow-lg ring-1 ring-black/10">
                      <button
                        className="w-full rounded-xl px-3 py-2 text-left hover:bg-[#f6f1e8]"
                        onClick={async () => {
                          setOpenMenuId(null);
                          await onExportSession(session.id);
                        }}
                        type="button"
                      >
                        Export PDF
                      </button>
                      <button
                        className="mt-1 w-full rounded-xl px-3 py-2 text-left text-[#9f2f2f] hover:bg-[#fff1ef]"
                        onClick={() => {
                          setOpenMenuId(null);
                          onDeleteSession(session.id);
                        }}
                        type="button"
                      >
                        Delete
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
