import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Options Signals Dashboard",
  description: "Frontend dashboard for the Options-MVP signal engine"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
