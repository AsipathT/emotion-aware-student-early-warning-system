import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { ConsentGate } from './consent/ConsentGate';
import { NotificationBell } from './NotificationBell';
import { useAuth } from '../hooks/useAuth';
import { Menu, X, Activity, User } from 'lucide-react';

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { user, isAuthenticated } = useAuth();

  // Close mobile drawer whenever the route changes
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Auth pages and Admin pages handle their own layout
  const isAuthOrAdmin =
    location.pathname === '/login' ||
    location.pathname === '/register' ||
    location.pathname.startsWith('/admin');

  if (isAuthOrAdmin) {
    return (
      <div className="min-h-screen bg-slate-50 font-sans">
        <ConsentGate />
        <main className="min-h-screen">
          {children}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans">
      <ConsentGate />

      {/* Desktop Fixed Left Sidebar (250px / w-64) */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 z-30 bg-white border-r border-slate-200 shadow-xs">
        <Sidebar />
      </aside>

      {/* Mobile Drawer Backdrop and Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden animate-in fade-in duration-200">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close menu backdrop"
          />

          {/* Drawer Content */}
          <div className="relative flex-1 flex flex-col max-w-xs w-full bg-white z-10 shadow-2xl">
            <div className="absolute top-3.5 right-3 z-20">
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 focus:outline-none transition"
                aria-label="Close sidebar menu"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <Sidebar onNavigate={() => setMobileMenuOpen(false)} />
          </div>
        </div>
      )}

      {/* Main Content Area (offset by fixed 250px / w-64 sidebar on desktop) */}
      <div className="flex-1 flex flex-col md:pl-64 min-w-0">
        {/* Mobile Header (visible only on mobile < md) */}
        <header className="md:hidden sticky top-0 z-40 bg-white border-b border-slate-200 h-16 flex items-center justify-between px-4 sm:px-6 shadow-xs">
          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="p-2 -ml-1 rounded-lg text-slate-600 hover:text-indigo-600 hover:bg-slate-100 focus:outline-none transition"
              aria-label="Open navigation menu"
            >
              <Menu className="w-6 h-6" />
            </button>
            <Link to="/" className="flex items-center space-x-2">
              <div className="p-1.5 bg-indigo-600 rounded-lg text-white">
                <Activity className="h-5 w-5" />
              </div>
              <span className="text-base font-bold text-slate-900 tracking-tight">
                Emotion-Aware <span className="text-indigo-600">LMS</span>
              </span>
            </Link>
          </div>

          <div className="flex items-center space-x-2">
            {isAuthenticated && user ? (
              <>
                <NotificationBell />
                <Link
                  to="/profile"
                  className="flex items-center space-x-1.5 p-1 rounded-full hover:bg-slate-100 transition"
                  title="Profile"
                >
                  <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs">
                    {user.full_name?.charAt(0) || <User className="w-3.5 h-3.5" />}
                  </div>
                </Link>
              </>
            ) : (
              <Link
                to="/login"
                className="px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-xs transition"
              >
                Sign In
              </Link>
            )}
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1">
          {children}
        </main>
      </div>
    </div>
  );
};
