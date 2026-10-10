import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { revealStudentIdentity, IdentityRevealResponse } from '../../api/privacy';
import {
  Eye,
  Loader2,
  X,
  ShieldCheck,
  AlertTriangle,
  User,
  Mail,
  GraduationCap,
  Hash,
} from 'lucide-react';

export interface IdentityRevealModalProps {
  pid: string;
  buttonLabel?: string;
  className?: string;
  size?: 'sm' | 'md';
}

export const IdentityRevealModal: React.FC<IdentityRevealModalProps> = ({
  pid,
  buttonLabel = 'Reveal Identity',
  className = '',
  size = 'md',
}) => {
  const { user } = useAuth();

  // Role restriction: Only Counsellors, Academic Staff (Lecturers), and Admins can reveal identities
  const isAuthorized =
    user?.role === 'counsellor' ||
    user?.role === 'lecturer' ||
    user?.role === 'admin';

  const [isPromptOpen, setIsPromptOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [identity, setIdentity] = useState<IdentityRevealResponse | null>(null);
  const [errorToast, setErrorToast] = useState<string | null>(null);

  // Auto-dismiss error toast after 5 seconds
  useEffect(() => {
    if (errorToast) {
      const timer = setTimeout(() => setErrorToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [errorToast]);

  // If current user is not authorized, do not render the component
  if (!isAuthorized) {
    return null;
  }

  const handleTriggerClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setErrorToast(null);
    setReason('');
    setIsPromptOpen(true);
  };

  const handleConfirmReveal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (reason.trim().length < 10) {
      setErrorToast('Please enter a justification reason of at least 10 characters.');
      return;
    }

    setIsLoading(true);
    setErrorToast(null);

    try {
      const data = await revealStudentIdentity(pid, reason.trim());
      setIdentity(data);
      setIsPromptOpen(false);
      setIsOpen(true);
    } catch (err: any) {
      const detail =
        err?.response?.status === 403
          ? 'Unauthorized: You do not have permission to view real identities.'
          : err?.response?.data?.detail || 'Unauthorized or audit logging failed.';
      setErrorToast(detail);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCloseModal = () => {
    setIsOpen(false);
  };


  const buttonSizeClasses =
    size === 'sm'
      ? 'px-2.5 py-1 text-xs'
      : 'px-3 py-1.5 text-xs sm:text-sm';

  return (
    <>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={handleTriggerClick}
        disabled={isLoading}
        title={`Reveal real identity for ${pid}`}
        className={`inline-flex items-center space-x-1.5 font-medium rounded-lg transition-colors border shadow-sm ${buttonSizeClasses} ${
          isLoading
            ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
            : 'bg-indigo-50 hover:bg-indigo-100/80 text-indigo-700 border-indigo-200/80 active:bg-indigo-200'
        } ${className}`}
      >
        {isLoading ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />
            <span>Processing...</span>
          </>
        ) : (
          <>
            <Eye className="w-3.5 h-3.5 text-indigo-600" />
            <span>{buttonLabel}</span>
          </>
        )}
      </button>

      {/* Floating Error Toast */}
      {errorToast && (
        <div className="fixed bottom-5 right-5 z-50 max-w-md bg-rose-50 border border-rose-200 text-rose-800 px-4 py-3 rounded-xl shadow-lg flex items-start space-x-3 animate-fade-in">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 text-xs">
            <span className="font-semibold block text-rose-900">Access Error</span>
            <span>{errorToast}</span>
          </div>
          <button
            onClick={() => setErrorToast(null)}
            className="text-rose-500 hover:text-rose-700 p-0.5 rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Mandatory Justification Prompt Dialog */}
      {isPromptOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          onClick={() => !isLoading && setIsPromptOpen(false)}
        >
          <div
            className="bg-white w-full max-w-md rounded-2xl shadow-2xl border border-slate-200 p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center space-x-3 text-indigo-700">
              <div className="p-2 bg-indigo-50 rounded-xl border border-indigo-100">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">
                  Identity Reveal Justification
                </h3>
                <p className="text-[11px] text-slate-500 font-mono">
                  Subject: {pid}
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Institutional privacy policies require a verified justification for auditing prior to decrypting student identities.
            </p>

            <form onSubmit={handleConfirmReveal} className="space-y-3">
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-[11px] font-semibold text-slate-700 uppercase tracking-wider">
                    Justification Reason (Min 10 chars)
                  </label>
                  <span className={`text-[10px] font-mono ${reason.trim().length >= 10 ? 'text-emerald-600' : 'text-slate-400'}`}>
                    {reason.trim().length} / 10 min
                  </span>
                </div>
                <textarea
                  rows={3}
                  required
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Urgent mental health welfare follow-up reported by lecturer..."
                  className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-1">
                <button
                  type="button"
                  disabled={isLoading}
                  onClick={() => setIsPromptOpen(false)}
                  className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 rounded-xl transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading || reason.trim().length < 10}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 rounded-xl shadow-sm transition disabled:opacity-50 flex items-center space-x-1.5"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Auditing & Decrypting...</span>
                    </>
                  ) : (
                    <span>Confirm & Reveal</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}


      {/* Controlled Reveal Modal */}
      {isOpen && identity && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in"
          onClick={handleCloseModal}
        >
          <div
            className="bg-white w-full max-w-md rounded-2xl shadow-2xl border border-slate-200 overflow-hidden transform transition-all animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 bg-indigo-100 text-indigo-700 rounded-lg">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-sm sm:text-base">
                    Identity Vault &bull; Real Identity
                  </h3>
                  <p className="text-[11px] text-slate-500 font-mono">
                    Target PID: {identity.pid}
                  </p>
                </div>
              </div>
              <button
                onClick={handleCloseModal}
                className="text-slate-400 hover:text-slate-600 rounded-lg p-1 hover:bg-slate-200/60 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Audit Log Warning Banner */}
            <div className="px-6 py-3 bg-amber-50/80 border-b border-amber-200/60 flex items-start space-x-2.5 text-amber-900 text-xs">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <p className="leading-relaxed">
                <strong>Audit Notice:</strong> This identity reveal has been recorded
                in the compliance audit log with your account ID and timestamp.
              </p>
            </div>

            {/* Student Real Identity Card */}
            <div className="p-6 space-y-4">
              {/* Full Name */}
              <div className="flex items-start space-x-3 p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="p-2 bg-indigo-100 text-indigo-700 rounded-lg">
                  <User className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Student Full Name
                  </span>
                  <span className="text-sm font-bold text-slate-900 break-words">
                    {identity.name}
                  </span>
                </div>
              </div>

              {/* Institutional Student ID */}
              <div className="flex items-start space-x-3 p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="p-2 bg-emerald-100 text-emerald-700 rounded-lg">
                  <GraduationCap className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Institutional Registration ID
                  </span>
                  <span className="text-sm font-mono font-bold text-slate-900 break-words">
                    {identity.student_id}
                  </span>
                </div>
              </div>

              {/* Email Address */}
              <div className="flex items-start space-x-3 p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="p-2 bg-blue-100 text-blue-700 rounded-lg">
                  <Mail className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Institutional Email
                  </span>
                  <span className="text-sm font-medium text-slate-800 break-words">
                    {identity.email}
                  </span>
                </div>
              </div>

              {/* Pseudonym ID Pill */}
              <div className="flex items-start space-x-3 p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="p-2 bg-purple-100 text-purple-700 rounded-lg">
                  <Hash className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Pseudonym ID (PID)
                  </span>
                  <span className="text-xs font-mono font-semibold text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded-md inline-block">
                    {identity.pid}
                  </span>
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-end">
              <button
                type="button"
                onClick={handleCloseModal}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 active:bg-slate-400 text-slate-800 text-xs font-semibold rounded-xl transition"
              >
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default IdentityRevealModal;
