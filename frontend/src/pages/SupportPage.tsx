/**
 * src/pages/SupportPage.tsx
 *
 * Feature 38-A: Student Support Hub & Uptake Page (Component 4 Uptake Metric).
 * Displays offered and active support initiatives for the active student with
 * non-stigmatizing labels, friendly descriptions, and voluntary accept/decline responses.
 *
 * Contains marked expansion slots for F38-B, F38-C, F38-D, and F39.
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  HeartHandshake,
  CheckCircle2,
  XCircle,
  Calendar,
  UserCheck,
  Sparkles,
  Loader2,
  AlertTriangle,
  HelpCircle,
  X,
} from 'lucide-react';
import {
  supportApi,
  StudentSupportInterventionItem,
  DeclineReason,
} from '../api/support';

const DECLINE_CHIPS: { value: DeclineReason; label: string }[] = [
  { value: 'no_time', label: 'Schedule conflict / No time' },
  { value: 'not_needed', label: 'Not needed at this time' },
  { value: 'prefer_other_support', label: 'Prefer alternative support' },
  { value: 'other', label: 'Other reason' },
];

export const SupportPage: React.FC = () => {
  const queryClient = useQueryClient();

  // Dialog states
  const [acceptItem, setAcceptItem] = useState<StudentSupportInterventionItem | null>(null);
  const [declineItem, setDeclineItem] = useState<StudentSupportInterventionItem | null>(null);
  const [selectedDeclineReason, setSelectedDeclineReason] = useState<DeclineReason>('not_needed');
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Fetch student's own support interventions
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['my-support-interventions'],
    queryFn: () => supportApi.getMyInterventions(),
  });

  // Respond mutation
  const respondMutation = useMutation({
    mutationFn: ({
      id,
      response,
      decline_reason,
    }: {
      id: string;
      response: 'accept' | 'decline';
      decline_reason?: DeclineReason | null;
    }) => supportApi.respondToIntervention(id, { response, decline_reason }),
    onSuccess: (res) => {
      setAcceptItem(null);
      setDeclineItem(null);
      setErrorMessage(null);
      setFeedbackMessage(res.message);
      queryClient.invalidateQueries({ queryKey: ['my-support-interventions'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      setTimeout(() => setFeedbackMessage(null), 5000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Unable to submit your response. Please try again.';
      setErrorMessage(detail);
    },
  });

  const handleConfirmAccept = () => {
    if (!acceptItem) return;
    respondMutation.mutate({
      id: acceptItem.id,
      response: 'accept',
    });
  };

  const handleConfirmDecline = () => {
    if (!declineItem) return;
    respondMutation.mutate({
      id: declineItem.id,
      response: 'decline',
      decline_reason: selectedDeclineReason,
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'offered':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'accepted':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'in_progress':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      case 'completed':
        return 'bg-teal-100 text-teal-800 border-teal-200';
      case 'declined':
        return 'bg-slate-100 text-slate-700 border-slate-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-2xl bg-indigo-50 text-indigo-600">
              <HeartHandshake className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                My Support
              </h1>
              <p className="text-sm text-slate-500">
                Personalized academic guidance, learning resources, and wellbeing consultations prepared for you.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Global Alert / Feedback */}
      {feedbackMessage && (
        <div className="mb-6 bg-emerald-50 border border-emerald-200 rounded-2xl p-4 text-xs text-emerald-800 flex items-center gap-2.5 shadow-sm">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{feedbackMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="mb-6 bg-rose-50 border border-rose-200 rounded-2xl p-4 text-xs text-rose-800 flex items-center gap-2.5 shadow-sm">
          <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Content Area */}
      {isLoading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto mb-3" />
          <p className="text-xs font-medium text-slate-500">
            Checking your personalized support options...
          </p>
        </div>
      ) : isError ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-xs text-rose-800">
          <p className="font-semibold">Unable to load support options.</p>
          <p className="mt-1 text-slate-600">
            {(error as any)?.response?.data?.detail || 'An unexpected error occurred.'}
          </p>
          <button
            onClick={() => refetch()}
            className="mt-3 px-4 py-2 bg-rose-600 text-white rounded-xl font-semibold hover:bg-rose-700 transition"
          >
            Retry
          </button>
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <Sparkles className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-slate-800">Nothing offered right now</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            You currently have no active or pending support initiatives. When advisors prepare course guidance or mentoring for you, it will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {data.items.map((item) => (
            <div
              key={item.id}
              className={`bg-white rounded-2xl border p-6 shadow-sm transition space-y-4 ${
                item.status === 'offered'
                  ? 'border-indigo-200 ring-1 ring-indigo-100'
                  : 'border-slate-200'
              }`}
            >
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 pb-4 border-b border-slate-100">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold border uppercase tracking-wider ${getStatusBadge(
                        item.status
                      )}`}
                    >
                      {item.status.replace(/_/g, ' ')}
                    </span>
                    {item.offered_at && (
                      <span className="text-[11px] text-slate-400">
                        Offered on {new Date(item.offered_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                  <h3 className="text-lg font-bold text-slate-900">
                    {item.student_label}
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed max-w-2xl">
                    {item.description}
                  </p>
                </div>

                {/* Status Badges & Advisor Meta */}
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 min-w-[220px] space-y-1.5 text-xs">
                  {item.assigned_staff_name && (
                    <div className="flex items-center gap-1.5 text-slate-800 font-medium">
                      <UserCheck className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Advisor: {item.assigned_staff_name}</span>
                    </div>
                  )}
                  {item.scheduled_for && (
                    <div className="flex items-center gap-1.5 text-slate-700">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>{new Date(item.scheduled_for).toLocaleString()}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Status State Context */}
              {item.status === 'accepted' && (
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-100 text-xs text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span>
                    You accepted this support initiative. Your advisor has been notified and will coordinate next steps.
                  </span>
                </div>
              )}

              {item.status === 'declined' && (
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-center gap-2">
                  <HelpCircle className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <span>
                    You declined this support session. You can always reach out to course instructors or advisors if your needs change.
                  </span>
                </div>
              )}

              {/* Response Action Buttons (Only when Offered) */}
              {item.status === 'offered' && (
                <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-indigo-50/40 p-4 rounded-xl border border-indigo-100">
                  <p className="text-xs text-indigo-900 font-medium">
                    Would you like to participate in this support initiative?
                  </p>
                  <div className="flex items-center gap-2.5">
                    <button
                      onClick={() => {
                        setAcceptItem(item);
                        setErrorMessage(null);
                      }}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Accept Support</span>
                    </button>
                    <button
                      onClick={() => {
                        setDeclineItem(item);
                        setSelectedDeclineReason('not_needed');
                        setErrorMessage(null);
                      }}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-200 text-slate-600 hover:text-rose-600 hover:bg-slate-50 transition"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Decline</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Marked Extension Slots */}
              {/* Dushan: F38-B booking */}
              {/* F38-C resources */}
              {/* F38-D mentor */}
              {/* F39 feedback */}
            </div>
          ))}
        </div>
      )}

      {/* Gentle Accept Confirmation Dialog */}
      {acceptItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-600">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <h4 className="text-base font-bold text-slate-900">
                Confirm Support Acceptance
              </h4>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed mb-5">
              You are about to accept{' '}
              <strong className="text-slate-900">{acceptItem.student_label}</strong>.
              Your designated advisor will be informed so they can prepare the learning materials or session schedule for you.
            </p>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                disabled={respondMutation.isPending}
                onClick={() => setAcceptItem(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={respondMutation.isPending}
                onClick={handleConfirmAccept}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
              >
                {respondMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Accepting...
                  </>
                ) : (
                  'Confirm & Accept'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Gentle Decline Reason Modal */}
      {declineItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-slate-100 text-slate-600">
                  <XCircle className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-slate-900">
                    Decline Support Option
                  </h4>
                  <p className="text-[11px] text-slate-500">
                    Your choice is completely voluntary and confidential.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setDeclineItem(null)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-600 mb-3">
              Please let us know your reason for declining{' '}
              <strong className="text-slate-900">{declineItem.student_label}</strong>:
            </p>

            {/* Categorical Reason Chips */}
            <div className="space-y-2 mb-5">
              {DECLINE_CHIPS.map((chip) => (
                <label
                  key={chip.value}
                  className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer text-xs transition ${
                    selectedDeclineReason === chip.value
                      ? 'border-indigo-600 bg-indigo-50/50 font-semibold text-indigo-900 ring-1 ring-indigo-500'
                      : 'border-slate-200 hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="decline-reason"
                    value={chip.value}
                    checked={selectedDeclineReason === chip.value}
                    onChange={() => setSelectedDeclineReason(chip.value)}
                    className="text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>{chip.label}</span>
                </label>
              ))}
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                disabled={respondMutation.isPending}
                onClick={() => setDeclineItem(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                Keep Offered
              </button>
              <button
                type="button"
                disabled={respondMutation.isPending}
                onClick={handleConfirmDecline}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 shadow-sm transition disabled:opacity-50"
              >
                {respondMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  'Confirm Decline'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
