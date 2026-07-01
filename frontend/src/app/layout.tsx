import type { Metadata } from "next";
import { Bodoni_Moda, Roboto } from "next/font/google";
import type { ReactNode } from "react";
import "@/styles/globals.scss";
import { Providers } from "./providers";

const bodoniModa = Bodoni_Moda({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "700"],
  variable: "--font-headline",
});

const roboto = Roboto({
  subsets: ["latin"],
  display: "swap",
  weight: ["300", "400", "500", "700"],
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
