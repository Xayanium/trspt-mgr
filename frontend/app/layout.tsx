import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "校园机动车综合管理平台",
  description: "Campus traffic management admin system"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
