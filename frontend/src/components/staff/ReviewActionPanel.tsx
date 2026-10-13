/**
 * src/components/staff/ReviewActionPanel.tsx
 *
 * Feature 33: Human-in-the-Loop Recommendation Decision Action Panel (C4 FR7).
 * Enables staff to Approve (with candidate rank selection), Modify (with catalog type),
 * or Reject an algorithmic recommendation with mandatory justification.
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  Edit3,
  XCircle,
  AlertTriangle,
  Loader2,
  ShieldCheck,
  ArrowRight,
} from 'lucide-react';
import {
  staffReviewApi,
  StaffReviewResponse,
  ReviewDecision,
} from '../../api/staffReview';
import { StaffRecommendationDetailResponse } from '../../api/staffRecommendations';

const CATALOG_OPTIONS = [
  { value: 'academic_support', label: 'Academic Support & Tutoring' },
  { value: 'counselling_mental_health', label: 'Mental Health & Wellbeing Counselling' },
  { value: 'time_management_guidance', label: 'Time Management & Study Skills Coaching' },
  { value: 'peer_mentoring', label: 'Peer Mentoring & Collaborative Study' },
  { value: 'additional_learning_resources', label: 'Supplementary Learning Resources' },
  { value: 'referral_services', label: 'Specialized Student Services Referral' },
  { value: 'peer_tutoring', label: 'Peer Tutoring & Study Group' },
  { value: 'academic_advising', label: 'Academic Advising Consultation' },
  { value: 'counsellor_outreach', label: 'Proactive Counsellor Outreach' },
];

export interface ReviewActionPanelProps {
  recommendation: StaffRecommendationDetailResponse;
  onReviewed?: (response: StaffReviewResponse) => void;
}

export const ReviewActionPanel: React.FC<ReviewActionPanelProps> = ({
  recommendation,
  onReviewed,
}) => {
  const isAlreadyDecided = ['approved', 'modified', 'rejected'].includes(
    recommendation.status.toLowerCase()
  );

  const [decision, setDecision] = useState<ReviewDecision>('approved');
  const [selectedRank, setSelectedRank] = useState<number>(1);
  const [modifiedType, setModifiedType] = useState<string>('counselling_mental_health');
  const [reason, setReason] = useState<string>('');

  const [isConfirmOpen, setIsConfirmOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<StaffReviewResponse | null>(null);

  // If already decided on initial load or post-submission
  if (isAlreadyDecided || result) {
    const finalDecision = result?.decision || recommendation.status;
    const finalInterventionId = result?.intervention_id;

    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
          <div className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-slate-900 text-sm">
                Human Review Finalized
              </h3>
              <span className="px-2.5 py-0.5 rounded text-xs font-semibold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200">
                {finalDecision}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Ground truth feedback outcome recorded and dispatched to Component 4 feedback loop.
            </p>
          </div>
        </div>

        <div className="pt-4 flex flex-wrap items-center justify-between gap-4">
          <div className="text-xs text-slate-600">
            {finalDecision === 'rejected' ? (
              <span>This recommendation was rejected. No student intervention was generated.</span>
            ) : (
              <span>
                Intervention strategy approved and baseline analytics snapshot locked.
              </span>
            )}
          </div>

          {finalInterventionId && (
            <Link
              to={`/staff/interventions/${encodeURIComponent(finalInterventionId)}`}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition"
            >
              Open Operational Intervention Record
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>
      </div>
    );
  }

  const handleOpenConfirm = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    // Validation checks
    if (decision === 'modified') {
      if (!modifiedType) {
        setErrorMessage('Please select an alternative intervention type from the catalog.');
        return;
      }
      if (reason.trim().length < 10) {
        setErrorMessage('Please provide a justification reason of at least 10 characters.');
        return;
      }
    } else if (decision === 'rejected') {
      if (reason.trim().length < 10) {
        setErrorMessage('Please provide a justification reason of at least 10 characters when rejecting.');
        return;
      }
    }

    setIsConfirmOpen(true);
  };

  const handleConfirmSubmit = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await staffReviewApi.submitRecommendationReview(
        recommendation.recommendation_id,
        {
          decision,
          selected_rank: decision === 'approved' ? selectedRank : null,
          modified_intervention_type: decision === 'modified' ? modifiedType : null,
          reason: reason.trim() || null,
          course_id: recommendation.context_course_id,
        }
      );

      setResult(response);
      setIsConfirmOpen(false);
      if (onReviewed) {
        onReviewed(response);
      }
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to record staff recommendation review.';
      setErrorMessage(detail);
      setIsConfirmOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-indigo-200 shadow-sm p-6 ring-1 ring-indigo-50">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-5">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="w-5 h-5 text-indigo-600" />
          <div>
            <h3 className="font-bold text-slate-900 text-sm">
              Staff Review & Decision Control (C4 FR7)
            </h3>
            <p className="text-xs text-slate-500">
              Select an action to finalize this recommendation and establish the baseline tracking state.
            </p>
          </div>
        </div>
        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
          Decisions are final
        </span>
      </div>

      {errorMessage && (
        <div className="mb-5 bg-rose-50 border border-rose-200 rounded-xl p-3.5 text-xs text-rose-800 flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <strong>Action error: </strong>
            <span>{errorMessage}</span>
          </div>
        </div>
      )}

      <form onSubmit={handleOpenConfirm} className="space-y-5">
        {/* Step 1: Decision Mode Radio Selection */}
        <div>
          <label className="text-xs font-bold text-slate-700 block mb-2">
            1. Select Review Decision
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Option A: Approve */}
            <label
              className={`p-3.5 rounded-xl border cursor-pointer flex items-start gap-3 transition ${
                decision === 'approved'
                  ? 'border-indigo-600 bg-indigo-50/50 ring-1 ring-indigo-500'
                  : 'border-slate-200 hover:bg-slate-50'
              }`}
            >
              <input
                type="radio"
                name="decision-choice"
                value="approved"
                checked={decision === 'approved'}
                onChange={() => setDecision('approved')}
                className="mt-0.5 text-indigo-600 focus:ring-indigo-500"
              />
              <div>
                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Approve Candidate</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1 leading-snug">
                  Accept an algorithmic candidate and spawn an operational intervention.
                </p>
              </div>
            </label>

            {/* Option B: Modify */}
            <label
              className={`p-3.5 rounded-xl border cursor-pointer flex items-start gap-3 transition ${
                decision === 'modified'
                  ? 'border-indigo-600 bg-indigo-50/50 ring-1 ring-indigo-500'
                  : 'border-slate-200 hover:bg-slate-50'
              }`}
            >
              <input
                type="radio"
                name="decision-choice"
                value="modified"
                checked={decision === 'modified'}
                onChange={() => setDecision('modified')}
                className="mt-0.5 text-indigo-600 focus:ring-indigo-500"
              />
              <div>
                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900">
                  <Edit3 className="w-3.5 h-3.5 text-sky-600" />
                  <span>Modify Strategy</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1 leading-snug">
                  Override with an alternative catalog type suited to student profile.
                </p>
              </div>
            </label>

            {/* Option C: Reject */}
            <label
              className={`p-3.5 rounded-xl border cursor-pointer flex items-start gap-3 transition ${
                decision === 'rejected'
                  ? 'border-indigo-600 bg-indigo-50/50 ring-1 ring-indigo-500'
                  : 'border-slate-200 hover:bg-slate-50'
              }`}
            >
              <input
                type="radio"
                name="decision-choice"
                value="rejected"
                checked={decision === 'rejected'}
                onChange={() => setDecision('rejected')}
                className="mt-0.5 text-indigo-600 focus:ring-indigo-500"
              />
              <div>
                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900">
                  <XCircle className="w-3.5 h-3.5 text-rose-600" />
                  <span>Reject Recommendation</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1 leading-snug">
                  Dismiss all suggested options with mandatory human rationale.
                </p>
              </div>
            </label>
          </div>
        </div>

        {/* Step 2A: If Approved -> Choose Rank */}
        {decision === 'approved' && (
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
            <label className="text-xs font-bold text-slate-700 block mb-1">
              Select Candidate Priority Rank to Implement:
            </label>
            <div className="space-y-2">
              {recommendation.candidates.map((cand) => (
                <label
                  key={cand.rank}
                  className={`flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition ${
                    selectedRank === cand.rank
                      ? 'border-indigo-500 bg-white ring-1 ring-indigo-400'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="radio"
                      name="rank-choice"
                      value={cand.rank}
                      checked={selectedRank === cand.rank}
                      onChange={() => setSelectedRank(cand.rank)}
                      className="text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="text-xs font-mono font-semibold text-slate-600">
                      Rank #{cand.rank}
                    </span>
                    <span className="text-xs font-bold text-slate-800">
                      {cand.label}
                    </span>
                  </div>
                  <span className="text-xs font-mono text-slate-500 font-semibold">
                    {(cand.suitability_score * 100).toFixed(0)}% Match
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Step 2B: If Modified -> Choose Alternative Catalog Type */}
        {decision === 'modified' && (
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
            <label className="text-xs font-bold text-slate-700 block">
              Select Alternative Intervention from Canonical Catalog:
            </label>
            <select
              value={modifiedType}
              onChange={(e) => setModifiedType(e.target.value)}
              className="w-full text-xs border-slate-200 rounded-lg px-3 py-2 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            >
              {CATALOG_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label} ({opt.value})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Step 3: Justification Reason Input */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-bold text-slate-700">
              {decision === 'approved'
                ? 'Clinical Notes / Justification (Optional):'
                : 'Mandatory Review Rationale (10 - 500 characters):'}
            </label>
            <span className="text-[11px] text-slate-400 font-mono">
              {reason.length} / 500
            </span>
          </div>
          <textarea
            rows={3}
            maxLength={500}
            placeholder={
              decision === 'approved'
                ? 'Add internal counselor notes regarding approval (stored privately, omitted from contracts)...'
                : 'Explain why the algorithmic options were modified or rejected (required for ground truth)...'
            }
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full text-xs border-slate-200 rounded-xl p-3 bg-slate-50/50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
          />
        </div>

        {/* Action Button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition"
          >
            Review & Finalize Decision
          </button>
        </div>
      </form>

      {/* Confirmation Modal Dialog */}
      {isConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 rounded-xl bg-amber-50 text-amber-600">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h4 className="text-base font-bold text-slate-900">
                Confirm Human Decision
              </h4>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed mb-4">
              You are about to record a decision of{' '}
              <strong className="text-slate-900 uppercase">{decision}</strong> for
              student <strong className="font-mono text-slate-900">{recommendation.pid}</strong>.
              This decision is irreversible and will lock the baseline tracking snapshot.
            </p>

            <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 text-xs text-slate-700 space-y-1 mb-5">
              <div>
                <strong>Decision:</strong>{' '}
                <span className="capitalize">{decision}</span>
              </div>
              {decision === 'approved' && (
                <div>
                  <strong>Selected Rank:</strong> #{selectedRank}
                </div>
              )}
              {decision === 'modified' && (
                <div>
                  <strong>Modified Type:</strong> {modifiedType}
                </div>
              )}
              {reason && (
                <div className="italic text-slate-500 truncate">
                  "{reason}"
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => setIsConfirmOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleConfirmSubmit}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Recording...
                  </>
                ) : (
                  'Confirm & Finalize'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
