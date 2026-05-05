import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { ToastProvider } from "@/components/ToastNotifier";

export const metadata: Metadata = {
  title: "Estate Mind — AI Real Estate Intelligence",
  description: "PropTech platform — trust scoring, territorial analytics, market intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="dash-body">
        <ToastProvider>
          <Sidebar />
          <main className="dash-main">
            {children}
          </main>
        </ToastProvider>
      </body>
    </html>
  );
}
