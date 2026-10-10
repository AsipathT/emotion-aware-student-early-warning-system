import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../hooks/useAuth';
import { consentApi, ConsentStatusResponse } from '../../api/consent';
import {
  ShieldCheck,
  Lock,
  HeartHandshake,
  FileCheck2,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  XCircle,
} from 'lucide-react';

export const ConsentGate: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Check consent status for authenticated students
  const {
    data: consentStatus,
    isLoading: isCheckingConsent,
  } = useQuery<ConsentStatusResponse>({
    queryKey: ['consentStatus'],
    queryFn: consentApi.getMyConsentStatus,
    enabled: !!isAuthenticated && user?.role === 'student',
    staleTime: 1000 * 60 * 2, // 2 minutes
  });

  // Decision submission mutation
  const decisionMutation = useMutation({
    mutationFn: (decision: 'accepted' | 'declined') =>
      consentApi.submitConsentDecision(decision),
    onSuccess: () => {
      setErrorMessage(null);
      // Invalidate queries to refresh state and close gate
      queryClient.invalidateQueries({ queryKey: ['consentStatus'] });
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
      queryClient.invalidateQueries({ queryKey: ['userProfile'] });
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail ||
        'Failed to record your decision. Please verify your connection and try again.';
      setErrorMessage(detail);
    },
  });

  // Only display blocking gate if user is student and consent is explicitly required
  if (!isAuthenticated || user?.role !== 'student' || isCheckingConsent) {
    return null;
  }

  if (!consentStatus?.consent_required) {
    return null;
  }

  const activeNotice = consentStatus.active_notice;
  const isSubmitting = decisionMutation.isPending;

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-gate-title"
    >
      <div className="max-w-2xl w-full bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-200">
        {/* Banner Header */}
        <div className="relative bg-gradient-to-br from-indigo-700 via-indigo-800 to-slate-900 text-white p-6 sm:p-8">
          <div className="flex items-center space-x-3.5">
            <div className="p-3 bg-white/10 backdrop-blur-md rounded-2xl border border-white/20 text-indigo-200 shadow-inner">
              <ShieldCheck className="w-8 h-8 text-indigo-300" />
            </div>
            <div>
              <span className="inline-block px-2.5 py-0.5 mb-1 bg-indigo-500/30 text-indigo-200 text-[11px] font-bold tracking-wider uppercase rounded-full border border-indigo-400/30 font-mono">
                Ethics Notice v{activeNotice?.version ?? 1}
              </span>
              <h2 id="consent-gate-title" className="text-xl sm:text-2xl font-black tracking-tight text-white">
                Student Ethics & Data Usage Notice
              </h2>
            </div>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 sm:p-8 space-y-6">
          {/* Error Alert */}
          {errorMessage && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start space-x-3 text-sm">
              <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Primary Notice Text Box */}
          <div className="p-5 bg-slate-50 border border-slate-200/90 rounded-2xl">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Official Statement of Intent
            </h3>
            <p className="text-sm text-slate-800 leading-relaxed font-normal whitespace-pre-line">
              {activeNotice?.text ||
                'To help us notice when students may need support, this LMS records how you use it: logins, page and video activity, submissions, grades, attendance and the messages you post. Messages and activity are processed with your identity replaced by a code before any analysis. Results are only seen by authorised counsellors and academic staff, who use them to offer help. They are never used for grading or disciplinary action. You can withdraw at any time in your profile, and this will not affect your access to your courses.'}
            </p>
          </div>

          {/* Core Commitments List */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
            <div className="flex items-start space-x-3 p-3 rounded-xl bg-indigo-50/50 border border-indigo-100/60">
              <Lock className="w-4 h-4 text-indigo-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs">
                <p className="font-semibold text-indigo-950">Pseudonymized Pipeline</p>
                <p className="text-indigo-800/80 mt-0.5">Identities are replaced with code STU_XXXXXXXX before processing.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 rounded-xl bg-emerald-50/50 border border-emerald-100/60">
              <HeartHandshake className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs">
                <p className="font-semibold text-emerald-950">Supportive Interventions</p>
                <p className="text-emerald-800/80 mt-0.5">Used strictly by counsellors and lecturers to extend academic support.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 rounded-xl bg-slate-100/60 border border-slate-200/60">
              <XCircle className="w-4 h-4 text-slate-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs">
                <p className="font-semibold text-slate-900">Zero Academic Penalties</p>
                <p className="text-slate-600 mt-0.5">Never used for grading, penal assessments, or disciplinary sanctions.</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 rounded-xl bg-amber-50/50 border border-amber-100/60">
              <FileCheck2 className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs">
                <p className="font-semibold text-amber-950">Unrestricted Autonomy</p>
                <p className="text-amber-800/80 mt-0.5">You can withdraw anytime from your Profile without course disruption.</p>
              </div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="pt-4 border-t border-slate-100 flex flex-col-reverse sm:flex-row items-center justify-between gap-3">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => decisionMutation.mutate('declined')}
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-100 active:bg-slate-200 font-semibold text-sm transition focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50 text-center"
            >
              Decline & Enter LMS
            </button>

            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => decisionMutation.mutate('accepted')}
              className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm shadow-md hover:shadow transition flex items-center justify-center space-x-2 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Recording Decision...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Accept & Continue</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
