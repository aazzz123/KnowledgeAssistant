import type { Metadata } from "next";

import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "KnowledgeAssistant",
  description: "Frontend workspace for the KnowledgeAssistant project."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
