import type { Metadata, Viewport } from "next";
import "./globals.css";
import DesktopBlocker from "./components/DesktopBlocker";

export const metadata: Metadata = {
  title: "Smart Spectator Mobile",
  description: "AI-Powered Camera Observer & Real-Time Monitoring",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Smart Spectator",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: "#0A0D14",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-[#0A0D14] text-[#F9FAFB] min-h-screen antialiased select-none">
        <DesktopBlocker />
        {children}
      </body>
    </html>
  );
}
