import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Backlot · Capture Explorer",
  description:
    "Browse multimodal synthetic captures from Unreal Engine 5 — frames, actor annotations, and camera metadata.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-40 border-b border-[color:var(--border-subtle)] bg-[color:var(--bg-0)]/80 backdrop-blur-xl">
          <nav className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between gap-6">
            <Link
              href="/"
              className="group flex items-center gap-3 text-[13px] tracking-tight font-semibold text-[color:var(--text-1)]"
            >
              <span
                aria-hidden
                className="relative h-6 w-6 rounded-md bg-gradient-to-br from-[#60a5fa] to-[#4ade80] shadow-[0_0_12px_rgba(96,165,250,0.35)] overflow-hidden"
              >
                <span className="absolute inset-[3px] rounded-[3px] bg-[color:var(--bg-0)]" />
                <span className="absolute inset-[7px] rounded-[1px] bg-gradient-to-br from-[#60a5fa] to-[#4ade80]" />
              </span>
              <span>
                Backlot
                <span className="ml-2 text-[color:var(--text-3)] font-normal">
                  Capture Explorer
                </span>
              </span>
            </Link>

            <div className="flex items-center gap-1 text-[13px]">
              <NavLink href="/">Projects</NavLink>
              <a
                href={`${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/docs`}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-2 rounded-md px-3 py-1.5 text-[color:var(--text-3)] hover:text-[color:var(--text-1)] transition"
              >
                API ↗
              </a>
            </div>
          </nav>
        </header>

        <main className="flex-1 max-w-[1400px] w-full mx-auto px-6 py-10">
          {children}
        </main>

        <footer className="border-t border-[color:var(--border-subtle)] mt-16 py-6 text-center font-mono text-[11px] text-[color:var(--text-muted)]">
          Backlot take-home · synthetic data capture & explorer
        </footer>
      </body>
    </html>
  );
}

function NavLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="rounded-md px-3 py-1.5 text-[color:var(--text-2)] hover:text-[color:var(--text-1)] hover:bg-[color:var(--bg-2)] transition"
    >
      {children}
    </Link>
  );
}
