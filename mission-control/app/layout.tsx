import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Hermes Mission Control',
  description: 'Zentrales Gehirn - graph, activity, tasks',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
