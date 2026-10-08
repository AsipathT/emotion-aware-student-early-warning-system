import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { LogOut, User, BookOpen, Activity } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-3">
            <Activity className="h-7 w-7 text-indigo-600" />
            <Link to="/" className="text-xl font-bold text-gray-900 tracking-tight">
              Emotion-Aware <span className="text-indigo-600">LMS</span>
            </Link>
          </div>

          <div className="flex items-center space-x-4">
            {isAuthenticated && user ? (
              <>
                <Link
                  to="/"
                  className="flex items-center text-sm font-medium text-gray-600 hover:text-indigo-600 transition"
                >
                  <BookOpen className="w-4 h-4 mr-1.5" />
                  Dashboard
                </Link>

                <div className="flex items-center space-x-2 pl-4 border-l border-gray-200">
                  <div className="flex items-center space-x-1.5 text-sm text-gray-700 bg-gray-100 px-3 py-1.5 rounded-full">
                    <User className="w-4 h-4 text-gray-500" />
                    <span className="font-medium">{user.full_name}</span>
                    <span className="text-xs uppercase bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded font-semibold ml-1">
                      {user.role}
                    </span>
                  </div>

                  <button
                    onClick={logout}
                    title="Logout"
                    className="p-1.5 text-gray-500 hover:text-red-600 rounded-lg hover:bg-red-50 transition"
                  >
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              </>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};
