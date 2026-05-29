import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PulseAlpha AI",
  description: "Indian Market Intelligence Engine",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg0 text-t1 font-body">{children}</body>
    </html>
  );
}
