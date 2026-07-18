'use client';

import React, { ReactNode, useCallback, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Lock } from 'lucide-react';
import { Toaster } from 'react-hot-toast';
import { ThemeToggle } from '@/components/ThemeToggle';
import DashboardAuthGate from '@/components/DashboardAuthGate';
import { logout } from '@/lib/auth';
import {
  type AccessTier,
  getAppSubtitle,
  getNavItems,
  getTierLabel,
  isJuniorTier,
} from '@/lib/app-mode';

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const [accessTier, setAccessTier] = useState<AccessTier>('senior');

  const handleAuthenticated = useCallback((tier: AccessTier) => {
    setAccessTier(tier);
  }, []);

  const navItems = getNavItems(accessTier);
  const junior = isJuniorTier(accessTier);
  const appSubtitle = getAppSubtitle(accessTier);

  return (
    <DashboardAuthGate onAuthenticated={handleAuthenticated}>
      <div className="flex h-screen bg-slate-50 dark:bg-slate-950">
        <Toaster position="top-right" />
        <aside className="w-64 bg-brand-900 text-white shadow-lg flex flex-col">
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
              {appSubtitle}
            </h2>
            {junior && (
              <p className="mt-2 text-center text-xs text-gold-200">
                {getTierLabel('junior')} mode
              </p>
            )}
          </div>

          <nav className="flex-1 p-4 space-y-1">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== '/dashboard' && pathname.startsWith(item.href));

              if (item.locked) {
                return (
                  <div
                    key={item.href}
                    title="Senior access only — use a senior developer account to open this section"
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium border-l-4 border-transparent text-white/40 cursor-not-allowed select-none"
                  >
                    <Lock className="h-3.5 w-3.5 flex-shrink-0" aria-hidden />
                    <span>{item.label}</span>
                  </div>
                );
              }

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

          <div className="p-4 border-t border-brand-800 space-y-1">
            {!junior && (
              <Link
                href="/dashboard/settings"
                className="block px-4 py-2 rounded-lg text-sm text-white/70 hover:bg-brand-800 hover:text-white transition-colors"
              >
                Settings
              </Link>
            )}
            <button
              type="button"
              onClick={logout}
              className="w-full text-left px-4 py-2 rounded-lg text-sm text-white/70 hover:bg-brand-800 hover:text-white transition-colors"
            >
              Sign out
            </button>
          </div>
        </aside>

        <main className="flex-1 overflow-auto">
          <header className="bg-white shadow dark:bg-slate-900 dark:shadow-slate-950/50 dark:border-b dark:border-slate-800">
            <div className="px-6 py-4 flex justify-between items-center">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {junior ? 'Junior Workspace' : 'Dashboard'}
              </h1>
              <ThemeToggle />
            </div>
          </header>

          <div className="p-6">{children}</div>
        </main>
      </div>
    </DashboardAuthGate>
  );
}
