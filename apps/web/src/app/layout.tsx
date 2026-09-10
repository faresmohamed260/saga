import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "S.A.G.A.",
    template: "%s · S.A.G.A.",
  },
  description:
    "Story intelligence for reconstructing canon, understanding worlds, and creating grounded narrative media.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
