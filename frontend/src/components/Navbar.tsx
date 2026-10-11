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
} from 'lucide-react';


export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();

  const isCurrent = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  // Do not render top navigation on auth screens
  if (location.pathname === '/login' || location.pathname === '/register') {
    return null;
  }

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-3">
            <Activity className="h-7 w-7 text-indigo-600" />
            <Link to="/" className="text-xl font-bold text-slate-900 tracking-tight">
              Emotion-Aware <span className="text-indigo-600">LMS</span>
            </Link>
          </div>

          <div className="flex items-center space-x-4">
            {isAuthenticated && user ? (
              <>
                <div className="flex items-center space-x-2 sm:space-x-3">
                  <Link
                    to="/"
                    className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                      isCurrent('/')
                        ? 'text-indigo-600 bg-indigo-50/80 font-semibold'
                        : 'text-slate-600 hover:text-indigo-600 hover:bg-slate-50'
                    }`}
                  >
                    <BookOpen className="w-4 h-4 mr-1.5" />
                    Dashboard
                  </Link>

                  <Link
                    to="/courses"
                    className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                      isCurrent('/courses')
                        ? 'text-indigo-600 bg-indigo-50/80 font-semibold'
                        : 'text-slate-600 hover:text-indigo-600 hover:bg-slate-50'
                    }`}
                  >
                    <GraduationCap className="w-4 h-4 mr-1.5" />
                    Courses
                  </Link>

                  {/* Conditionally render My Courses for Students */}
                  {user.role === 'student' && (
                    <Link
                      to="/my-courses"
                      className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                        isCurrent('/my-courses')
                          ? 'text-indigo-600 bg-indigo-50/80 font-semibold'
                          : 'text-slate-600 hover:text-indigo-600 hover:bg-slate-50'
                      }`}
                    >
                      <BookmarkCheck className="w-4 h-4 mr-1.5" />
                      My Courses
                    </Link>
                  )}

                  <Link
                    to="/profile"
                    className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                      isCurrent('/profile')
                        ? 'text-indigo-600 bg-indigo-50/80 font-semibold'
                        : 'text-slate-600 hover:text-indigo-600 hover:bg-slate-50'
                    }`}
                  >
                    <UserCircle className="w-4 h-4 mr-1.5" />
                    Profile
                  </Link>

                  {user.role === 'admin' && (
                    <Link
                      to="/admin"
                      className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                        isCurrent('/admin')
                          ? 'text-purple-700 bg-purple-50 font-semibold'
                          : 'text-slate-600 hover:text-purple-700 hover:bg-slate-50'
                      }`}
                    >
                      <Shield className="w-4 h-4 mr-1.5 text-purple-600" />
                      Admin
                    </Link>
                  )}

                  {(user.role === 'admin' || user.role === 'auditor') && (
                    <Link
                      to="/admin/audit"
                      className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                        isCurrent('/admin/audit')
                          ? 'text-indigo-600 bg-indigo-50 font-semibold'
                          : 'text-slate-600 hover:text-indigo-600 hover:bg-slate-50'
                      }`}
                    >
                      <ShieldCheck className="w-4 h-4 mr-1.5 text-indigo-600" />
                      Audit Log
                    </Link>
                  )}
                </div>


                <div className="flex items-center space-x-2 pl-3 sm:pl-4 border-l border-slate-200">
                  <Link
                    to="/profile"
                    title="View and edit your profile"
                    className="flex items-center space-x-1.5 text-sm text-slate-700 bg-slate-100 hover:bg-slate-200/80 px-3 py-1.5 rounded-full transition"
                  >
                    <User className="w-4 h-4 text-slate-500" />
                    <span className="font-medium hidden sm:inline">{user.full_name}</span>
                    <span className="text-[10px] uppercase bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded font-bold ml-1">
                      {user.role}
                    </span>
                  </Link>

                  <button
                    onClick={logout}
                    title="Logout"
                    className="p-1.5 text-slate-500 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition"
                  >
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              </>
            ) : (
              <div className="flex items-center space-x-2">
                <Link
                  to="/login"
                  className="px-4 py-2 text-sm font-medium text-slate-700 hover:text-indigo-600 transition"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-sm transition"
                >
                  Register
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};
