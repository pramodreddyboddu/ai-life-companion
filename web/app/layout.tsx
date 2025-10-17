import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { NavLink } from "../components/NavLink";

export const metadata: Metadata = {
  title: "AI Companion Dashboard",
  description: "Manage chat, reminders, and settings.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header>
          <nav>
            <NavLink href="/">Chat</NavLink>
            <NavLink href="/reminders">Reminders</NavLink>
            <NavLink href="/settings">Settings</NavLink>
          </nav>
        </header>
        <main>
          <div className="container">{children}</div>
        </main>
      </body>
    </html>
  );
}
