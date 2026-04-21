import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/NavBar";
import { ToastProvider } from "@/components/ToastNotifier";

export const metadata: Metadata = {
  title: "Estate Mind — PropTech Tunisienne",
  description: "Plateforme d'analyse immobilière — trust scoring, analyse territoriale, intelligence marché",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <ToastProvider>
          <NavBar />
          <main style={{ maxWidth:1280, margin:"0 auto", padding:"28px 28px" }}>
            {children}
          </main>
        </ToastProvider>
      </body>
    </html>
  );
}
