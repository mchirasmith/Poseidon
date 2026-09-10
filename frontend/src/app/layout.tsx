import type { Metadata } from "next";
import { Space_Grotesk, Geist_Mono } from "next/font/google";
import "./globals.css";
import KineticGrid from "@/components/ui/kinetic-grid";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const description =
  "Subsurface 3D ocean temperature reconstruction from satellite surface observations for the North Indian Ocean (SIH 2026).";

export const metadata: Metadata = {
  title: "Varuna | Deep Ocean Temperature AI",
  description,
  openGraph: {
    title: "Varuna | Deep Ocean Temperature AI",
    description,
    type: "website",
  },
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
        <KineticGrid>
          {children}
        </KineticGrid>
      </body>
    </html>
  );
}
