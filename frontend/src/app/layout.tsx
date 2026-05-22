import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@/styles/globals.scss";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Fotosintesis AI",
  description: "Asistente botanico mobile-first para el cuidado de plantas",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
