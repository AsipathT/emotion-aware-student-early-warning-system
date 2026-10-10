import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { consentApi, ConsentStatusResponse } from '../../api/consent';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileText,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export const PrivacySettings: React.FC = () => {
  const queryClient = useQueryClient();
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showNoticeText, setShowNoticeText] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  // Fetch current consent status
  const {
    data: consentStatus,
    isLoading,
    isError,
  } = useQuery<ConsentStatusResponse>({
    queryKey: ['consentStatus'],
    queryFn: consentApi.getMyConsentStatus,
  });

  // Withdraw consent mutation
  const withdrawMutation = useMutation({
    mutationFn: consentApi.withdrawConsent,
    onSuccess: () => {
      setShowConfirmModal(false);
      queryClient.invalidateQueries({ queryKey: ['consentStatus'] });
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
      setFeedbackMessage({
        type: 'success',
        text: 'Your consent has been successfully withdrawn. Ongoing emotion and engagement data collection has ceased.',
      });
      setTimeout(() => setFeedbackMessage(null), 6000);
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail ||
        'Failed to withdraw consent. Please try again.';
      setFeedbackMessage({
        type: 'error',
        text: detail,
      });
    },
  });

  // Re-opt-in consent mutation
  const optInMutation = useMutation({
    mutationFn: () => consentApi.submitConsentDecision('accepted'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consentStatus'] });
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
      setFeedbackMessage({
        type: 'success',
        text: 'Thank you! Your active consent has been recorded and academic early warning support is active.',
      });
      setTimeout(() => setFeedbackMessage(null), 6000);
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail ||
        'Failed to update consent. Please try again.';
      setFeedbackMessage({
        type: 'error',
        text: detail,
      });
    },
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm flex items-center justify-center space-x-3">
        <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-medium text-slate-500">Loading privacy settings...</span>
      </div>
    );
  }

  if (isError || !consentStatus) {
    return null;
  }

  const decision = consentStatus.latest_decision;
  const isAccepted = decision === 'accepted';
  const isDeclined = decision === 'declined';
  const isWithdrawn = decision === 'withdrawn';

  return (
    <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5">
        <div className="flex items-center space-x-3.5">
          <div className="p-2.5 bg-indigo-50 border border-indigo-100/80 rounded-xl text-indigo-600">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Privacy, Ethics & Data Consent
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Manage your participation in the emotion-aware early warning predictive pipeline.
            </p>
          </div>
        </div>

        {/* Current Posture Badge */}
        <div>
          {isAccepted && (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
              Consent Granted (Active)
            </span>
          )}
          {isDeclined && (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
              <AlertTriangle className="w-3.5 h-3.5 mr-1.5 text-amber-600" />
              Data Collection Declined
            </span>
          )}
          {isWithdrawn && (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
              <XCircle className="w-3.5 h-3.5 mr-1.5 text-rose-600" />
              Consent Withdrawn
            </span>
          )}
          {!decision && (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
              <Clock className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
              Decision Pending
            </span>
          )}
        </div>
      </div>

      {/* Inline Feedback Banner */}
      {feedbackMessage && (
        <div
          className={`p-4 rounded-xl border flex items-start space-x-3 text-xs leading-relaxed ${
            feedbackMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}
        >
          {feedbackMessage.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
          )}
          <span className="flex-1 font-medium">{feedbackMessage.text}</span>
          <button
            type="button"
            onClick={() => setFeedbackMessage(null)}
            className="text-slate-400 hover:text-slate-600 ml-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Metadata & Policy Info Card */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/60">
          <span className="font-semibold text-slate-500 block uppercase tracking-wider text-[11px] mb-1">
            Active Policy Version
          </span>
          <span className="text-sm font-bold text-slate-800 font-mono">
            Version {consentStatus.notice_version ?? 1}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/60">
          <span className="font-semibold text-slate-500 block uppercase tracking-wider text-[11px] mb-1">
            Last Decision Date
          </span>
          <span className="text-sm font-medium text-slate-800">
            {consentStatus.timestamp
              ? new Date(consentStatus.timestamp).toLocaleString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : 'No recorded decision yet'}
          </span>
        </div>
      </div>

      {/* Collapsible Notice Content */}
      <div className="border border-slate-200/80 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowNoticeText(!showNoticeText)}
          className="w-full px-4 py-3 bg-slate-50/70 hover:bg-slate-100/70 text-left flex items-center justify-between transition text-xs font-semibold text-slate-700"
        >
          <span className="flex items-center space-x-2">
            <FileText className="w-4 h-4 text-indigo-600" />
            <span>Review Active Ethics Notice Text</span>
          </span>
          {showNoticeText ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </button>

        {showNoticeText && (
          <div className="p-4 bg-white text-xs text-slate-700 leading-relaxed border-t border-slate-200/80 whitespace-pre-line">
            {consentStatus.active_notice?.text ||
              'To help us notice when students may need support, this LMS records how you use it: logins, page and video activity, submissions, grades, attendance and the messages you post. Messages and activity are processed with your identity replaced by a code before any analysis. Results are only seen by authorised counsellors and academic staff, who use them to offer help. They are never used for grading or disciplinary action. You can withdraw at any time in your profile, and this will not affect your access to your courses.'}
          </div>
        )}
      </div>

      {/* Action Section */}
      <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-xs text-slate-500 leading-relaxed">
          {isAccepted ? (
            <p>
              Your affective analytics are pseudonymized. You may withdraw consent at any time without affecting your LMS access or grades.
            </p>
          ) : (
            <p>
              You have currently opted out of emotion-aware analytics. You may grant consent whenever you wish.
            </p>
          )}
        </div>

        <div className="flex-shrink-0">
          {isAccepted && (
            <button
              type="button"
              onClick={() => setShowConfirmModal(true)}
              disabled={withdrawMutation.isPending}
              className="px-4 py-2 text-xs font-semibold text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-xl transition focus:outline-none focus:ring-2 focus:ring-rose-500/20"
            >
              Withdraw Consent
            </button>
          )}

          {(isDeclined || isWithdrawn || !decision) && (
            <button
              type="button"
              onClick={() => optInMutation.mutate()}
              disabled={optInMutation.isPending}
              className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-sm transition focus:outline-none focus:ring-2 focus:ring-indigo-500/30 flex items-center space-x-1.5"
            >
              {optInMutation.isPending ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Grant Consent</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Confirmation Dialog for Withdrawing Consent */}
      {showConfirmModal && (
        <div
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-slate-100 p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center space-x-3 text-rose-600">
              <div className="p-2.5 bg-rose-50 rounded-xl border border-rose-100">
                <ShieldAlert className="w-6 h-6 text-rose-600" />
              </div>
              <h3 className="text-base font-bold text-slate-900">
                Confirm Consent Withdrawal
              </h3>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Withdrawing consent will stop new longitudinal behavioral and emotional data collection.
              Your course access, enrolled modules, and academic grades will <strong>not</strong> be affected.
              This withdrawal will be recorded in the security audit logs.
            </p>

            <div className="pt-2 flex justify-end space-x-2.5">
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                disabled={withdrawMutation.isPending}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 rounded-xl transition"
              >
                Keep Consent
              </button>
              <button
                type="button"
                onClick={() => withdrawMutation.mutate()}
                disabled={withdrawMutation.isPending}
                className="px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-xl shadow-sm transition flex items-center space-x-1.5"
              >
                {withdrawMutation.isPending ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <span>Confirm Withdrawal</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
