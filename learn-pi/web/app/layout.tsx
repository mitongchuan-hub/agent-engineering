import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Learn Pi | Coding Agent 源码课程",
  description: "从 Pi 源码学习 Coding Agent 的六个系统。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
