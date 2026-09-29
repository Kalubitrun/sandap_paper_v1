import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Question Paper Studio | Sandap Software Solution",
  description:
    "Create professional print-ready question papers from a teacher's DOCX.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-slate-100 font-sans text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
