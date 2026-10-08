import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Activity, Lock, Mail, AlertCircle } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, isLoggingIn } = useAuth();
  const [email, setEmail] = useState('admin@lms.edu');
  const [password, setPassword] = useState('Admin1234');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    try {
      await login({ email, password });
      navigate('/');
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Invalid email or password. Please try again.';
      setErrorMessage(detail);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-2xl shadow-sm border border-gray-100">
        <div className="text-center">
          <div className="inline-flex p-3 bg-indigo-50 rounded-2xl text-indigo-600 mb-3">
            <Activity className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-extrabold text-gray-900 tracking-tight">
            Sign in to Emotion-Aware LMS
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Student Early Warning System & Intervention Platform
          </p>
        </div>

        {errorMessage && (
          <div className="flex items-center p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
              Email Address
            </label>
            <div className="relative rounded-lg shadow-sm">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                <Mail className="h-5 w-5" />
              </div>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@university.edu"
                className="block w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
              Password
            </label>
            <div className="relative rounded-lg shadow-sm">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                <Lock className="h-5 w-5" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="block w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoggingIn}
            className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition"
          >
            {isLoggingIn ? 'Signing in...' : 'Sign in'}
          </button>

          <div className="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-600">
            <span className="font-semibold text-gray-800">Seed Accounts:</span>
            <ul className="mt-1 list-disc list-inside space-y-0.5">
              <li>Admin: <code className="bg-gray-200 px-1 py-0.5 rounded">admin@lms.edu</code> / <code className="bg-gray-200 px-1 py-0.5 rounded">Admin1234</code></li>
              <li>Lecturer: <code className="bg-gray-200 px-1 py-0.5 rounded">lecturer@lms.edu</code> / <code className="bg-gray-200 px-1 py-0.5 rounded">Lecturer1234</code></li>
              <li>Student: <code className="bg-gray-200 px-1 py-0.5 rounded">student@lms.edu</code> / <code className="bg-gray-200 px-1 py-0.5 rounded">Student1234</code></li>
            </ul>
          </div>
        </form>
      </div>
    </div>
  );
};
