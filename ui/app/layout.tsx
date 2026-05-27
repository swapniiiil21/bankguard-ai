import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'BankGuard AI | Enterprise Operations Center',
  description: 'Real-time Autonomous Fraud Intelligence Interface',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-50 antialiased h-screen overflow-hidden`}>
        {/* We can add Global Navigation, Sidebar, and Toast Providers here */}
        <main className="w-full h-full">
          {children}
        </main>
      </body>
    </html>
  );
}
