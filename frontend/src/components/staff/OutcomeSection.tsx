/**
 * src/components/staff/OutcomeSection.tsx
 *
 * Feature 35: Staff Intervention Outcome Recording & Analytics Delta Section (C4 FR8/FR9).
 * Displays objective before/after evidence metrics (baseline vs latest analytics),
 * weeks-to-improvement calculation, and outcome recording form/locked card.
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Award,
  TrendingDown,
  TrendingUp,
  Minus,
  CheckCircle2,
  Clock,
  Lock,
  Loader2,
  AlertTriangle,
  ArrowRight,
  FileText,
} from 'lucide-react';
import {
  staffOutcomesApi,
  OutcomeCategory,
  OutcomeResult,
} from '../../api/staffOutcomes';

interface OutcomeSectionProps {
  interventionId: string;
  status: string;
  onOutcomeSaved?: () => void;
}

export const OutcomeSection: React.FC<OutcomeSectionProps> = ({
  interventionId,
  status,
  onOutcomeSaved,
}) => {
  const queryClient = useQueryClient();

  const [result, setResult] = useState<OutcomeResult>('completed');
  const [category, setCategory] = useState<OutcomeCategory>('improved');
  const [hasManuallySetCategory, setHasManuallySetCategory] = useState<boolean>(false);
  const [summary, setSummary] = useState<string>('');
  const [staffNotes, setStaffNotes] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);

  // Fetch objective outcome suggestion & baseline comparison
  const {
    data: suggestion,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['outcome-suggestion', interventionId],
    queryFn: async () => {
      const data = await staffOutcomesApi.getOutcomeSuggestion(interventionId);
      if (!hasManuallySetCategory && data.suggested_direction) {
        setCategory(data.suggested_direction);
      }
      return data;
    },
  });

  // Record outcome mutation
  const recordMutation = useMutation({
    mutationFn: (payload: {
      result: OutcomeResult;
      staff_category: OutcomeCategory;
      summary?: string;
      staff_notes?: string;
    }) => staffOutcomesApi.recordOutcome(interventionId, payload),
    onSuccess: () => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['outcome-suggestion', interventionId] });
      queryClient.invalidateQueries({ queryKey: ['staff-intervention-detail', interventionId] });
      queryClient.invalidateQueries({ queryKey: ['staff-interventions'] });
      if (onOutcomeSaved) {
        onOutcomeSaved();
      }
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to record intervention outcome.';
      setFormError(detail);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    recordMutation.mutate({
      result,
      staff_category: category,
      summary: summary.trim() || undefined,
      staff_notes: staffNotes.trim() || undefined,
    });
  };

  const getTierBadge = (tier: string) => {
    const t = String(tier || '').toLowerCase();
    switch (t) {
      case 'low':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'medium':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'high':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      case 'critical':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center shadow-sm">
        <Loader2 className="w-6 h-6 text-indigo-600 animate-spin mx-auto mb-2" />
        <p className="text-xs text-slate-500">Loading outcome evaluation metrics...</p>
      </div>
    );
  }

  if (isError || !suggestion) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-center justify-between">
          <span>Failed to load objective analytics metrics.</span>
          <button
            onClick={() => refetch()}
            className="px-3 py-1 bg-amber-600 text-white rounded-lg font-semibold hover:bg-amber-700 transition"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { baseline, latest, delta, weeks_to_improvement, is_recorded, outcome } = suggestion;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
            <Award className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-sm">
              Intervention Outcome Evaluation & Evidence (C4 FR8/FR9)
            </h3>
            <p className="text-xs text-slate-500">
              Evaluates objective before/after risk changes and captures staff-verified outcome evidence for adaptive ranking.
            </p>
          </div>
        </div>

        {/* Suggestion Direction Badge */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-slate-500">Suggested Direction:</span>
          <span
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold border uppercase tracking-wider ${
              delta.direction === 'improved'
                ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                : delta.direction === 'worsened'
                ? 'bg-rose-100 text-rose-800 border-rose-200'
                : 'bg-slate-100 text-slate-700 border-slate-200'
            }`}
          >
            {delta.direction === 'improved' && <TrendingDown className="w-3.5 h-3.5 text-emerald-600" />}
            {delta.direction === 'worsened' && <TrendingUp className="w-3.5 h-3.5 text-rose-600" />}
            {delta.direction === 'no_change' && <Minus className="w-3.5 h-3.5 text-slate-500" />}
            <span>{delta.direction.replace(/_/g, ' ')}</span>
          </span>
        </div>
      </div>

      {/* Objective Before / After Metrics Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Risk Score & Tier */}
        <div className="bg-slate-50/75 rounded-xl p-4 border border-slate-100 space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-700">
            <span>Risk Score & Tier</span>
            {delta.risk_score_delta != null && (
              <span
                className={`text-[11px] font-mono px-2 py-0.5 rounded-full ${
                  delta.risk_score_delta < 0
                    ? 'bg-emerald-100 text-emerald-800'
                    : delta.risk_score_delta > 0
                    ? 'bg-rose-100 text-rose-800'
                    : 'bg-slate-200 text-slate-700'
                }`}
              >
                {delta.risk_score_delta > 0 ? `+${delta.risk_score_delta}` : delta.risk_score_delta}
              </span>
            )}
          </div>

          <div className="flex items-center justify-between text-xs pt-1">
            <div className="space-y-1">
              <span className="text-[10px] text-slate-400 block uppercase">Baseline (W{baseline.week_index ?? 0})</span>
              <span className="font-mono font-bold text-slate-800">
                {baseline.risk_score != null ? baseline.risk_score.toFixed(3) : 'N/A'}
              </span>
              <div>
                <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase border ${getTierBadge(baseline.risk_tier)}`}>
                  {baseline.risk_tier || 'N/A'}
                </span>
              </div>
            </div>

            <ArrowRight className="w-4 h-4 text-slate-300 flex-shrink-0" />

            <div className="space-y-1 text-right">
              <span className="text-[10px] text-slate-400 block uppercase">Latest (W{latest.week_index ?? 0})</span>
              <span className="font-mono font-bold text-slate-800">
                {latest.risk_score != null ? latest.risk_score.toFixed(3) : 'N/A'}
              </span>
              <div>
                <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase border ${getTierBadge(latest.risk_tier)}`}>
                  {latest.risk_tier || 'N/A'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Trajectory Transition */}
        <div className="bg-slate-50/75 rounded-xl p-4 border border-slate-100 space-y-3">
          <div className="text-xs font-bold text-slate-700">
            <span>Engagement Trajectory</span>
          </div>

          <div className="flex items-center justify-between text-xs pt-1">
            <div className="space-y-1">
              <span className="text-[10px] text-slate-400 block uppercase">Baseline</span>
              <span className="font-semibold text-slate-800 capitalize">
                {baseline.trajectory_label || 'unknown'}
              </span>
            </div>

            <ArrowRight className="w-4 h-4 text-slate-300 flex-shrink-0" />

            <div className="space-y-1 text-right">
              <span className="text-[10px] text-slate-400 block uppercase">Follow-up</span>
              <span className="font-semibold text-slate-800 capitalize">
                {latest.trajectory_label || 'unknown'}
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Weeks to Improvement Metric */}
        <div className="bg-slate-50/75 rounded-xl p-4 border border-slate-100 space-y-2 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
            <Clock className="w-3.5 h-3.5 text-indigo-600" />
            <span>Time to Improvement (C4 Metric)</span>
          </div>

          <div className="py-1">
            {weeks_to_improvement != null ? (
              <div className="flex items-baseline gap-1.5">
                <span className="text-2xl font-bold font-mono text-emerald-600">
                  {weeks_to_improvement}
                </span>
                <span className="text-xs font-semibold text-emerald-800">
                  weeks to positive improvement
                </span>
              </div>
            ) : (
              <span className="text-xs text-slate-500 italic">
                No tier or trajectory improvement detected yet.
              </span>
            )}
          </div>

          <span className="text-[10px] text-slate-400">
            Measured from baseline week {baseline.week_index ?? 0} to first qualifying week.
          </span>
        </div>
      </div>

      {/* Case A: Outcome Already Recorded (Immutable View) */}
      {is_recorded && outcome && (
        <div className="bg-emerald-50/40 rounded-2xl border border-emerald-200 p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-100">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <div>
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Intervention Outcome Finalized & Locked
                </h4>
                <p className="text-[11px] text-slate-500">
                  Recorded for adaptive feedback loop research evidence. Immutable.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200">
                Result: {outcome.result}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-100 text-indigo-800 border border-indigo-200">
                Category: {outcome.category}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            {outcome.summary && (
              <div className="space-y-1">
                <span className="font-semibold text-slate-700 block">Observational Summary:</span>
                <p className="p-3 bg-white rounded-xl border border-emerald-100 text-slate-800 leading-relaxed">
                  {outcome.summary}
                </p>
              </div>
            )}

            {outcome.staff_notes && (
              <div className="space-y-1">
                <span className="font-semibold text-slate-700 flex items-center gap-1">
                  <Lock className="w-3.5 h-3.5 text-slate-400" />
                  <span>Confidential Clinical Notes (Private LMS):</span>
                </span>
                <p className="p-3 bg-white rounded-xl border border-emerald-100 text-slate-800 leading-relaxed font-sans">
                  {outcome.staff_notes}
                </p>
              </div>
            )}
          </div>

          <div className="text-[11px] text-slate-400 pt-2 border-t border-emerald-100 flex items-center justify-between">
            <span>Recorded by staff member ID: {outcome.recorded_by}</span>
            <span>Recorded on: {new Date(outcome.recorded_at).toLocaleString()}</span>
          </div>
        </div>
      )}

      {/* Case B: Outcome Not Recorded, Status Allows Recording (Form) */}
      {!is_recorded && suggestion.can_record && (
        <form onSubmit={handleSubmit} className="p-5 bg-slate-50/70 rounded-2xl border border-indigo-100 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200">
            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-indigo-600" />
              <span>Record Final Intervention Outcome</span>
            </h4>
            <span className="text-[11px] font-semibold text-indigo-700 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-200">
              Action will lock record as Completed
            </span>
          </div>

          {formError && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-xs text-rose-800 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          {/* Result Radio */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-700 block">
              1. Delivery Result:
            </label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-xs font-medium text-slate-800 cursor-pointer">
                <input
                  type="radio"
                  name="outcome-result"
                  value="completed"
                  checked={result === 'completed'}
                  onChange={() => setResult('completed')}
                  className="text-indigo-600 focus:ring-indigo-500"
                />
                <span>Completed successfully</span>
              </label>

              <label className="flex items-center gap-2 text-xs font-medium text-slate-800 cursor-pointer">
                <input
                  type="radio"
                  name="outcome-result"
                  value="not_completed"
                  checked={result === 'not_completed'}
                  onChange={() => setResult('not_completed')}
                  className="text-indigo-600 focus:ring-indigo-500"
                />
                <span>Not completed / Discontinued</span>
              </label>
            </div>
          </div>

          {/* Category Select */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-700 block">
              2. Staff Assessed Outcome Category:
            </label>
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value as OutcomeCategory);
                setHasManuallySetCategory(true);
              }}
              className="w-full text-xs border-slate-200 rounded-xl px-3 py-2 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            >
              <option value="improved">Improved (Positive behavioral or academic gains observed)</option>
              <option value="no_change">No Change (Metrics and engagement remained stable)</option>
              <option value="worsened">Worsened (Disengagement or indicators escalated)</option>
              <option value="unknown">Unknown / Insufficient observation data</option>
            </select>
          </div>

          {/* Public Summary */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-700">
                3. Observational Summary (max 300 chars, scrubbed for exports):
              </label>
              <span className="text-[11px] font-mono text-slate-400">
                {summary.length} / 300
              </span>
            </div>
            <input
              type="text"
              maxLength={300}
              placeholder="e.g. Student attended tutoring sessions and completed week 5 formative exercises..."
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="w-full text-xs border-slate-200 rounded-xl px-3 py-2 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Staff Private Notes */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-slate-400" />
                <span>4. Confidential Counselor Notes (max 2000 chars, private LMS only):</span>
              </label>
              <span className="text-[11px] font-mono text-slate-400">
                {staffNotes.length} / 2000
              </span>
            </div>
            <textarea
              rows={3}
              maxLength={2000}
              placeholder="Clinical observations, student feedback, or recommendations for next academic term..."
              value={staffNotes}
              onChange={(e) => setStaffNotes(e.target.value)}
              className="w-full text-xs border-slate-200 rounded-xl p-3 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={recordMutation.isPending}
              className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
            >
              {recordMutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Recording Outcome...
                </>
              ) : (
                'Finalize & Record Outcome'
              )}
            </button>
          </div>
        </form>
      )}

      {/* Case C: Not Recorded and Status Does Not Permit Recording */}
      {!is_recorded && !suggestion.can_record && (
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-slate-400 flex-shrink-0" />
          <span>
            Outcome recording is only permissible once the intervention is <strong>accepted</strong> by the student or <strong>in progress</strong> (current lifecycle status: <span className="font-semibold uppercase text-slate-800">{status}</span>).
          </span>
        </div>
      )}
    </div>
  );
};
