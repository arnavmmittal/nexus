import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Jarvis Terminal",
  description: "Home terminal dashboard powered by Nexus",
};

export default function TerminalLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="min-h-screen w-full bg-[#0a0a0a] text-white overflow-hidden">
      {children}
    </div>
  );
}
