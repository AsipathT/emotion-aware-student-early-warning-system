import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  LogOut,
  User,
  BookOpen,
  Activity,
  UserCircle,
  GraduationCap,
  Shield,
  ShieldCheck,
  BookmarkCheck,
  MessageCircle,
  HeartHandshake,
  Database,
  ShieldAlert,
} from 'lucide-react';

interface SidebarProps {
  onNavigate?: () => void;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ onNavigate, className = '' }) => {
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();

  const isCurrent = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const getLinkClasses = (path: string, colorScheme: 'indigo' | 'purple' | 'rose' = 'indigo') => {
    const active = isCurrent(path);
    if (active) {
      if (colorScheme === 'purple') {
        return 'bg-purple-50 text-purple-700 font-semibold shadow-xs';
      }
      if (colorScheme === 'rose') {
        return 'bg-rose-50 text-rose-600 font-semibold shadow-xs';
      }
      return 'bg-indigo-50 text-indigo-600 font-semibold shadow-xs';
    }
    return 'text-slate-600 hover:text-indigo-600 hover:bg-slate-50 font-medium';
  };

  const getIconClasses = (path: string, colorScheme: 'indigo' | 'purple' | 'rose' = 'indigo') => {
    const active = isCurrent(path);
    if (active) {
      if (colorScheme === 'purple') return 'text-purple-600';
      if (colorScheme === 'rose') return 'text-rose-600';
      return 'text-indigo-600';
    }
    return 'text-slate-400 group-hover:text-indigo-600';
  };

  return (
    <aside
      className={`w-64 bg-white text-slate-800 flex flex-col h-full border-r border-slate-200 select-none ${className}`}
    >
      {/* Brand Header */}
      <div className="h-16 px-5 border-b border-slate-200 flex items-center justify-between shrink-0">
        <Link
          to="/"
          onClick={onNavigate}
          className="flex items-center space-x-2.5 group"
        >
          <div className="p-1.5 bg-indigo-600 rounded-lg text-white shadow-xs group-hover:bg-indigo-700 transition">
            <Activity className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold text-slate-900 tracking-tight">
            Emotion-Aware <span className="text-indigo-600">LMS</span>
          </span>
        </Link>
      </div>

      {/* Navigation Links Area */}
      <div className="flex-1 py-4 px-3 overflow-y-auto space-y-6">
        {/* Main Learning & Navigation */}
        <div className="space-y-1">
          <div className="px-3 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Navigation
          </div>

          {isAuthenticated && user ? (
            <>
              {/* Dashboard */}
              <Link
                to="/"
                onClick={onNavigate}
                className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                  '/'
                )}`}
              >
                <BookOpen
                  className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                    '/'
                  )}`}
                />
                <span className="truncate">Dashboard</span>
              </Link>

              {/* Courses */}
              <Link
                to="/courses"
                onClick={onNavigate}
                className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                  '/courses'
                )}`}
              >
                <GraduationCap
                  className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                    '/courses'
                  )}`}
                />
                <span className="truncate">Courses</span>
              </Link>

              {/* My Courses (Student Only) */}
              {user.role === 'student' && (
                <Link
                  to="/my-courses"
                  onClick={onNavigate}
                  className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                    '/my-courses'
                  )}`}
                >
                  <BookmarkCheck
                    className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                      '/my-courses'
                    )}`}
                  />
                  <span className="truncate">My Courses</span>
                </Link>
              )}

              {/* Journal (Student Only) */}
              {user.role === 'student' && (
                <Link
                  to="/journal"
                  onClick={onNavigate}
                  className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                    '/journal'
                  )}`}
                >
                  <BookOpen
                    className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                      '/journal'
                    )}`}
                  />
                  <span className="truncate">Journal</span>
                </Link>
              )}

              {/* Messages */}
              {(user.role === 'student' ||
                user.role === 'lecturer' ||
                user.role === 'counsellor') && (
                <Link
                  to="/messages"
                  onClick={onNavigate}
                  className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                    '/messages'
                  )}`}
                >
                  <MessageCircle
                    className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                      '/messages'
                    )}`}
                  />
                  <span className="truncate">Messages</span>
                </Link>
              )}

              {/* Student Support */}
              {(user.role === 'counsellor' || user.role === 'admin') && (
                <Link
                  to="/staff"
                  onClick={onNavigate}
                  className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                    '/staff'
                  )}`}
                >
                  <HeartHandshake
                    className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                      '/staff'
                    )}`}
                  />
                  <span className="truncate">Student Support</span>
                </Link>
              )}

              {/* Profile */}
              <Link
                to="/profile"
                onClick={onNavigate}
                className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                  '/profile'
                )}`}
              >
                <UserCircle
                  className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                    '/profile'
                  )}`}
                />
                <span className="truncate">Profile</span>
              </Link>
            </>
          ) : (
            <>
              {/* Unauthenticated View */}
              <Link
                to="/login"
                onClick={onNavigate}
                className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                  '/login'
                )}`}
              >
                <UserCircle
                  className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                    '/login'
                  )}`}
                />
                <span className="truncate">Sign In</span>
              </Link>
              <Link
                to="/register"
                onClick={onNavigate}
                className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                  '/register'
                )}`}
              >
                <Activity
                  className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                    '/register'
                  )}`}
                />
                <span className="truncate">Register</span>
              </Link>
            </>
          )}
        </div>

        {/* Administration & Intelligence (Roles: Admin, Lecturer, Auditor) */}
        {isAuthenticated &&
          user &&
          (user.role === 'admin' ||
            user.role === 'lecturer' ||
            user.role === 'auditor') && (
            <div className="space-y-1">
              <div className="px-3 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Insights & Admin
              </div>

              {/* Admin Console */}
              {user.role === 'admin' && (
                <Link
                  to="/admin"
                  onClick={onNavigate}
                  className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                    '/admin',
                    'purple'
                  )}`}
                >
                  <Shield
                    className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                      '/admin',
                      'purple'
                    )}`}
                  />
                  <span className="truncate">Admin Console</span>
                </Link>
              )}

              {/* Audit Log */}
              {(user.role === 'admin' || user.role === 'auditor') && (
                <Link
                  to="/admin/audit"
                  onClick={onNavigate}
                  className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                    '/admin/audit'
                  )}`}
                >
                  <ShieldCheck
                    className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                      '/admin/audit'
                    )}`}
                  />
                  <span className="truncate">Audit Log</span>
                </Link>
              )}

              {/* Cohort Risk */}
              {(user.role === 'admin' || user.role === 'lecturer') && (
                <Link
                  to="/cohort-risk"
                  onClick={onNavigate}
                  className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                    '/cohort-risk',
                    'rose'
                  )}`}
                >
                  <ShieldAlert
                    className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                      '/cohort-risk',
                      'rose'
                    )}`}
                  />
                  <span className="truncate">Cohort Risk</span>
                </Link>
              )}

              {/* Data Export & Pipeline */}
              {(user.role === 'admin' || user.role === 'lecturer') && (
                <Link
                  to="/export"
                  onClick={onNavigate}
                  className={`group flex items-center px-3 py-2 rounded-xl text-sm transition ${getLinkClasses(
                    '/export'
                  )}`}
                >
                  <Database
                    className={`w-4 h-4 mr-3 shrink-0 transition ${getIconClasses(
                      '/export'
                    )}`}
                  />
                  <span className="truncate">Data & Pipeline</span>
                </Link>
              )}
            </div>
          )}
      </div>

      {/* Footer / User Profile & Logout */}
      {isAuthenticated && user ? (
        <div className="p-3 border-t border-slate-200 shrink-0 bg-slate-50/70">
          <div className="flex items-center justify-between p-2 rounded-xl bg-white border border-slate-200/80 shadow-xs">
            <Link
              to="/profile"
              onClick={onNavigate}
              title="View and edit your profile"
              className="flex items-center space-x-2.5 min-w-0 flex-1 hover:opacity-80 transition"
            >
              <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
                <User className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-slate-800 truncate">
                  {user.full_name}
                </p>
                <span className="inline-block text-[10px] uppercase font-bold text-indigo-700 bg-indigo-50 px-1.5 py-0.2 rounded">
                  {user.role}
                </span>
              </div>
            </Link>

            <button
              onClick={() => {
                logout();
                if (onNavigate) onNavigate();
              }}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition shrink-0 ml-1"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      ) : (
        <div className="p-4 border-t border-slate-200 shrink-0 space-y-2 bg-slate-50/50">
          <Link
            to="/login"
            onClick={onNavigate}
            className="w-full flex items-center justify-center px-3 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 rounded-xl transition"
          >
            Sign In
          </Link>
          <Link
            to="/register"
            onClick={onNavigate}
            className="w-full flex items-center justify-center px-3 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition"
          >
            Register
          </Link>
        </div>
      )}
    </aside>
  );
};
