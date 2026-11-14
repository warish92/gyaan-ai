import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "../components/layout/AppShell";

export const metadata: Metadata = {
  title: "Gyaan AI — Multi-Agent Educational Platform",
  description: "CBSE Class 10 learning platform powered by local multi-agent AI (CrewAI + Ollama).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-[#F7F9FC] text-[#172033] antialiased min-h-screen">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
