import type { Metadata } from "next";
import { NavBar } from "@/components/NavBar";
import { NewDataToast } from "@/components/NewDataToast";
import "./globals.css";

export const metadata: Metadata = {
  title:       "Estate Mind — PropTech Tunisie",
  description: "Plateforme immobilière intelligente pour le marché tunisien",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body>
        {/* Navigation globale */}
        <NavBar />

        {/* Contenu principal */}
        <main style={{
          maxWidth:  1280,
          margin:    "0 auto",
          padding:   "24px 20px",
          minHeight: "calc(100vh - 52px)",
        }}>
          {children}
        </main>

        {/* 🔔 Toast nouvelles données — se connecte au SSE /api/notifications/stream */}
        <NewDataToast />
      </body>
    </html>
  );
}
