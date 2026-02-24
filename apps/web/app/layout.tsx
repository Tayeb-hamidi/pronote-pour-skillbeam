import type { Metadata } from "next";
import { Orbitron, Space_Grotesk } from "next/font/google";
import "./globals.css";

const orbitron = Orbitron({ subsets: ["latin"], variable: "--font-orbitron" });
const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-space" });

export const metadata: Metadata = {
  title: "SkillBeam AI-édu Quiz",
  description: "Outil IA pour creer, relire et exporter des QCM pedagogiques vers Pronote"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className={`${orbitron.variable} ${spaceGrotesk.variable}`}>{children}</body>
    </html>
  );
}
