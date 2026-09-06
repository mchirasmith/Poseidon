import type { Metadata } from "next";
import { Space_Grotesk, Geist_Mono } from "next/font/google";
import "./globals.css";
import { TheInfiniteGrid } from "@/components/ui/the-infinite-grid";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Poseidon | Deep Ocean Temperature AI",
  description: "Subsurface 3D ocean temperature reconstruction from satellite surface observations for the North Indian Ocean (SIH 2026).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-black text-white relative">
        <TheInfiniteGrid theme="ocean">
          {children}
        </TheInfiniteGrid>
      </body>
    </html>
  );
}
