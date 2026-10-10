import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Activity, Lock, Mail, AlertCircle, CheckCircle, Eye, EyeOff, ArrowRight } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, user } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // If already authenticated, redirect directly to dashboard
  useEffect(() => {
    if (isAuthenticated && user) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  // Check if redirected from registration page with success message
  const successMessage = (location.state as { message?: string })?.message;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!email.trim() || !password) {
      setErrorMessage('Please enter both your email and password.');
      return;
    }

    setIsSubmitting(true);
    try {
      // Calls loginUser with form-urlencoded format & stores JWT in localStorage
      await login({ email: email.trim(), password });
      navigate('/', { replace: true });
    } catch (err: any) {
      const detail =
        err.response?.data?.detail ||
        (err.response?.status === 401
          ? 'Invalid email or password. Please verify your credentials.'
          : 'Unable to connect to authentication service. Please try again.');
      setErrorMessage(detail);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSeedSelect = (seedEmail: string, seedPass: string) => {
    setEmail(seedEmail);
    setPassword(seedPass);
    setErrorMessage(null);
  };

  return (
    <div className="min-h-[88vh] flex items-center justify-center px-4 sm:px-6 lg:px-8 py-10 bg-slate-50">
      <div className="max-w-md w-full space-y-6 bg-white p-8 sm:p-10 rounded-2xl shadow-sm border border-slate-200/80">
        {/* Brand Header */}
        <div className="text-center">
          <div className="inline-flex p-3 bg-indigo-50 border border-indigo-100/80 rounded-2xl text-indigo-600 mb-3 shadow-sm">
            <Activity className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">
            Sign in to Emotion-Aware LMS
          </h2>
          <p className="mt-1.5 text-sm text-slate-500">
            Student Early Warning & Multimodal Affective Intervention Platform
          </p>
        </div>

        {/* Success Alert (after registration) */}
        {successMessage && (
          <div className="flex items-start p-3.5 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-xl">
            <CheckCircle className="w-5 h-5 mr-2.5 mt-0.5 text-emerald-600 flex-shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Error Alert */}
        {errorMessage && (
          <div className="flex items-start p-3.5 text-sm text-rose-800 bg-rose-50 border border-rose-200 rounded-xl">
            <AlertCircle className="w-5 h-5 mr-2.5 mt-0.5 text-rose-600 flex-shrink-0" />
            <span className="leading-snug">{errorMessage}</span>
          </div>
        )}

        {/* Form */}
        <form className="space-y-4.5" onSubmit={handleSubmit}>
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Email Address
            </label>
            <div className="relative rounded-xl shadow-sm">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <Mail className="h-5 w-5" />
              </div>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@university.edu"
                className="block w-full pl-11 pr-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
              />
            </div>
          </div>

          <div className="mt-4">
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Password
              </label>
            </div>
            <div className="relative rounded-xl shadow-sm">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <Lock className="h-5 w-5" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="block w-full pl-11 pr-11 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition"
              >
                {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 flex items-center justify-center py-2.5 px-4 border border-transparent rounded-xl shadow-sm text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition"
          >
            {isSubmitting ? (
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Signing in...</span>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <span>Sign In</span>
                <ArrowRight className="w-4 h-4" />
              </div>
            )}
          </button>
        </form>

        {/* Link to Register */}
        <div className="text-center pt-2 border-t border-slate-100">
          <p className="text-sm text-slate-600">
            Don't have an account yet?{' '}
            <Link
              to="/register"
              className="font-semibold text-indigo-600 hover:text-indigo-700 transition"
            >
              Create an account
            </Link>
          </p>
        </div>

        {/* Demo / Seed Credentials Quick Selector */}
        <div className="p-3.5 bg-slate-50 border border-slate-200/60 rounded-xl text-xs text-slate-600">
          <div className="font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
            <span>Quick Fill Test Accounts:</span>
            <span className="text-[10px] text-indigo-600 font-mono">click to select</span>
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            <button
              type="button"
              onClick={() => handleSeedSelect('student@lms.edu', 'Student1234')}
              className="px-2 py-1.5 bg-white hover:bg-indigo-50 border border-slate-200 rounded-lg text-center font-medium text-slate-700 hover:text-indigo-700 transition"
            >
              Student
            </button>
            <button
              type="button"
              onClick={() => handleSeedSelect('lecturer@lms.edu', 'Lecturer1234')}
              className="px-2 py-1.5 bg-white hover:bg-indigo-50 border border-slate-200 rounded-lg text-center font-medium text-slate-700 hover:text-indigo-700 transition"
            >
              Lecturer
            </button>
            <button
              type="button"
              onClick={() => handleSeedSelect('admin@lms.edu', 'Admin1234')}
              className="px-2 py-1.5 bg-white hover:bg-indigo-50 border border-slate-200 rounded-lg text-center font-medium text-slate-700 hover:text-indigo-700 transition"
            >
              Admin
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
