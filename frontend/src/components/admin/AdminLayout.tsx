import React, { useState } from 'react';
import { Outlet, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { AdminSidebar } from './AdminSidebar';
import { StatusBadge } from './StatusBadge';
import {
  Menu,
  X,
  LogOut,
  ChevronRight,
} from 'lucide-react';

export const AdminLayout: React.FC = () => {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();

  // Compute breadcrumb title from path
  const pathSegments = location.pathname.split('/').filter(Boolean);
  const currentSection = pathSegments[1]
    ? pathSegments[1].charAt(0).toUpperCase() + pathSegments[1].slice(1)
    : 'Overview';

  return (
    <div className="flex h-screen bg-slate-100 overflow-hidden font-sans">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex md:shrink-0">
        <AdminSidebar />
      </div>

      {/* Mobile Sidebar Modal */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="relative flex-1 flex flex-col max-w-xs w-full bg-slate-900 z-10">
            <div className="absolute top-0 right-0 -mr-12 pt-4">
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="p-1 rounded-md text-white hover:text-slate-300 focus:outline-none"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <AdminSidebar onCloseMobile={() => setMobileSidebarOpen(false)} />
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="bg-white border-b border-slate-200 h-16 shrink-0 flex items-center justify-between px-4 sm:px-6 lg:px-8 z-10 shadow-xs">
          <div className="flex items-center space-x-3">
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 md:hidden focus:outline-none"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Breadcrumb */}
            <nav className="flex items-center text-sm font-medium text-slate-500">
              <Link to="/admin" className="hover:text-indigo-600 transition">
                Admin
              </Link>
              <ChevronRight className="w-4 h-4 mx-2 text-slate-400" />
              <span className="text-slate-900 font-semibold">{currentSection}</span>
            </nav>
          </div>

          {/* Right Header: User Info & Actions */}
          <div className="flex items-center space-x-4">
            {user && (
              <div className="flex items-center space-x-3">
                <div className="hidden sm:flex flex-col text-right">
                  <span className="text-xs font-semibold text-slate-900 leading-tight">
                    {user.full_name}
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {user.email}
                  </span>
                </div>
                <StatusBadge role={user.role} size="sm" />
              </div>
            )}

            <div className="h-6 w-px bg-slate-200 hidden sm:block" />

            <button
              onClick={logout}
              title="Sign out of Admin Session"
              className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
