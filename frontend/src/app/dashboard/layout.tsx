'use client';

import React, { ReactNode } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Toaster } from 'react-hot-toast';

interface DashboardLayoutProps {
  children: ReactNode;
}

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/dashboard/creation', label: 'Content Creation' },
  { href: '/dashboard/generator', label: 'Content Posting' },
  { href: '/dashboard/calendar', label: 'Calendar' },
  { href: '/dashboard/analytics', label: 'Analytics' },
  { href: '/dashboard/qa', label: 'QA Checker' },
  { href: '/dashboard/rivals', label: 'Rival Review' },
];

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen bg-slate-50">
      <Toaster position="top-right" />
      {/* Sidebar — Kafi maroon/red brand */}
      <aside className="w-64 bg-brand-900 text-white shadow-lg flex flex-col">
        {/* Logo + title */}
        <div className="p-5 border-b border-brand-800">
          <div className="bg-white rounded-lg p-3 mb-4 flex items-center justify-center">
            <Image
              src="/kafi-logo.png"
              alt="Kafi Commodities"
              width={180}
              height={60}
              className="object-contain w-full h-auto"
              priority
            />
          </div>
          <h2 className="text-sm font-semibold tracking-wide text-center text-white/90 uppercase">
            Social Media Agent
          </h2>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== '/dashboard' && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors border-l-4 ${
                  isActive
                    ? 'border-gold-400 bg-brand-800/60 text-gold-300'
                    : 'border-transparent text-white/85 hover:bg-brand-800 hover:text-white'
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-brand-800">
          <Link
            href="/dashboard/settings"
            className="block px-4 py-2 rounded-lg text-sm text-white/70 hover:bg-brand-800 hover:text-white transition-colors"
          >
            Settings
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <header className="bg-white shadow">
          <div className="px-6 py-4 flex justify-between items-center">
            <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          </div>
        </header>

        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
