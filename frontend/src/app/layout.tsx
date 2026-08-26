import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import "@/styles/globals.scss";
import { Providers } from "./providers";

const bodoniModa = localFont({
  src: "./fonts/bodoni-moda-latin.woff2",
  display: "swap",
  weight: "400 900",
  variable: "--font-headline",
});

const roboto = localFont({
  src: "./fonts/roboto-latin.woff2",
  display: "swap",
  weight: "300 700",
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Fotosíntesis",
  description: "Asistente botánico mobile-first para el cuidado de plantas",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html
      lang="es"
      className={`${bodoniModa.variable} ${roboto.variable}`}
    >
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
