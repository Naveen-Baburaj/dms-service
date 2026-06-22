import Link from 'next/link';
import { Sparkles } from 'lucide-react';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { Navbar } from '@/components/navbar/Navbar';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-6 relative">
          {children}

          {/* Floating AI chat button — hidden on the /chat page itself */}
          <Link
            href="/chat"
            className="fixed bottom-6 right-6 z-50 flex h-13 items-center gap-2.5 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 px-4 py-3 text-white shadow-lg shadow-violet-500/30 hover:shadow-xl hover:shadow-violet-500/40 hover:scale-105 transition-all group"
            style={{ bottom: '24px', right: '24px' }}
          >
            <Sparkles className="h-4 w-4 shrink-0" />
            <span className="text-sm font-semibold pr-0.5">Ask AI</span>
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-300 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-violet-200" />
            </span>
          </Link>
        </main>
      </div>
    </div>
  );
}
