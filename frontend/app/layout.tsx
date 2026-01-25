import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { ToastProvider } from "@/components/ui/Toast";

export const metadata: Metadata = {
  title: "Vipu - Personal Finance Tracker",
  description: "Track your weekly budget and monthly net worth",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 dark:bg-gray-900 antialiased">
        <Providers>
          <ToastProvider>
            <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
              <div className="max-w-4xl mx-auto px-4 py-4">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  Vipu
                </h1>
              </div>
            </header>
            <main className="max-w-4xl mx-auto px-4 py-6">{children}</main>
          </ToastProvider>
        </Providers>
      </body>
    </html>
  );
}
