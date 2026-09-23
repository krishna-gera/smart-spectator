import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Smart Spectator — Intelligent Visual Monitoring Dashboard",
  description: "Monitor your Smart Spectator cameras, AI status, events, and alerts in real time.",
  keywords: ["smart spectator", "visual monitoring", "AI camera", "surveillance dashboard"],
  openGraph: {
    title: "Smart Spectator Dashboard",
    description: "Intelligent visual monitoring platform",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased`}>{children}</body>
    </html>
  );
}
