/**
 * src/pages/StaffRecommendationDetailPage.tsx
 *
 * Feature 32: Detailed Ranked Candidate Inspection for an Intervention Recommendation.
 * Displays suitability scores, model rationales, and student context link.
 */

import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  ExternalLink,
  Award,
  BookOpen,
  Calendar,
  Users,
  Compass,
  Sparkles,
} from 'lucide-react';
import { StaffTabs } from '../components/staff/StaffTabs';
import {
  staffRecommendationsApi,
  StaffRecommendationDetailResponse,
  StaffRecommendationCandidateDetail,
} from '../api/staffRecommendations';

const TIER_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  critical: { bg: 'bg-rose-100', text: 'text-rose-800', border: 'border-rose-200' },
  high: { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-200' },
  medium: { bg: 'bg-amber-100', text: 'text-amber-800', border: 'border-amber-200' },
  low: { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-200' },
};

const DELIVERY_MODULE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  counselling_booking: Calendar,
  resource_share: BookOpen,
  peer_mentoring: Users,
  none: Compass,
};

const DELIVERY_MODULE_LABELS: Record<string, string> = {
  counselling_booking: 'Counselling Booking Module',
  resource_share: 'Resource Share Module',
  peer_mentoring: 'Peer Mentoring Module',
  none: 'Direct Institutional Action',
};

export const StaffRecommendationDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const {
    data: detail,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<StaffRecommendationDetailResponse>({
    queryKey: ['staffRecommendationDetail', id],
    queryFn: () => staffRecommendationsApi.getRecommendationDetail(id!),
    enabled: Boolean(id),
  });

  const getErrorMessage = (err: any): string => {
    return (
      err?.response?.data?.detail ||
      err?.message ||
      'Failed to load recommendation detail.'
    );
  };

  const renderTierChip = (tier: string | null) => {
    if (!tier) return null;
    const key = tier.toLowerCase();
    const style = TIER_STYLES[key] || {
      bg: 'bg-slate-100',
      text: 'text-slate-700',
      border: 'border-slate-200',
    };
    return (
      <span
        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider border ${style.bg} ${style.text} ${style.border}`}
      >
        {tier} Risk
      </span>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Breadcrumb */}
      <div className="mb-6">
        <div className="flex items-center justify-between gap-4 mb-3">
          <Link
            to="/staff/recommendations"
            className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Recommendations List
          </Link>
          <div className="text-xs text-slate-500 bg-slate-100 px-3 py-1 rounded-lg border border-slate-200 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
            Decision-Support • Audited Access
          </div>
        </div>

        {/* Staff Navigation Tabs */}
        <StaffTabs />
      </div>

      {/* Mandatory Human-in-the-Loop Governance Banner */}
      <div className="mb-6 bg-amber-50 border border-amber-200 rounded-2xl p-4 text-amber-900 shadow-sm flex items-start gap-3.5">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <h2 className="text-sm font-bold">
            Review required before any intervention is implemented
          </h2>
          <p className="text-xs text-amber-800 mt-0.5 leading-relaxed">
            Component 4 algorithmic recommendations are decision-support outputs. In accordance with ethical safeguarding principles, no automated student communication or intervention is dispatched without authorised staff review and explicit human approval.
          </p>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="bg-white rounded-2xl border border-slate-200 p-16 text-center shadow-sm">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-600">
            Loading recommendation batch details...
          </p>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div className="bg-rose-50 rounded-2xl border border-rose-200 p-6 text-rose-800 shadow-sm mb-6">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-sm">Failed to load recommendation</h3>
              <p className="text-xs text-rose-700 mt-1">{getErrorMessage(error)}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 text-xs font-semibold text-rose-700 hover:text-rose-900 underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Detail Content */}
      {detail && (
        <div className="space-y-6">
          {/* Recommendation Batch Header Card */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Intervention Recommendation
                  </span>
                  <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                    ID: {detail.recommendation_id}
                  </span>
                  <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-slate-100 text-slate-700">
                    PID: {detail.pid}
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                    Week {detail.week_index}
                  </span>
                  {renderTierChip(detail.risk_tier)}
                  <span className="px-2.5 py-0.5 rounded text-xs font-semibold uppercase tracking-wider bg-slate-100 text-slate-700 border border-slate-200">
                    Status: {detail.status}
                  </span>
                </div>
                <h1 className="text-xl font-bold text-slate-900 mt-2">
                  Ranked Adaptive Interventions for Student {detail.pid}
                </h1>
                <p className="text-xs text-slate-500 mt-0.5">
                  Evaluated across historical outcome patterns, affective distress, and trajectory indicators.
                </p>
              </div>

              {/* Link to Unified Student Context Page (F31) */}
              <div className="flex items-center">
                <Link
                  to={
                    detail.context_course_id
                      ? `/staff/students/${encodeURIComponent(
                          detail.pid
                        )}?course_id=${encodeURIComponent(detail.context_course_id)}`
                      : `/staff/students/${encodeURIComponent(detail.pid)}`
                  }
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100/80 hover:text-indigo-900 transition"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open Student Context Profile
                </Link>
              </div>
            </div>
          </div>

          {/* Ranked Candidate Intervention Cards */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-indigo-600" />
                <h2 className="text-base font-bold text-slate-900">
                  Ranked Candidates ({detail.candidates.length})
                </h2>
              </div>
              <span className="text-xs text-slate-500">
                Sorted by Component 4 priority rank
              </span>
            </div>

            <div className="space-y-4">
              {detail.candidates.map((cand: StaffRecommendationCandidateDetail) => {
                const IconComp =
                  DELIVERY_MODULE_ICONS[cand.delivery_module] || Compass;
                const deliveryLabel =
                  DELIVERY_MODULE_LABELS[cand.delivery_module] ||
                  cand.delivery_module;
                const isTopRank = cand.rank === 1;

                const hasScore =
                  cand.suitability_score !== null &&
                  cand.suitability_score !== undefined;
                const hasRationale = Boolean(
                  cand.rationale && cand.rationale.trim().length > 0
                );

                return (
                  <div
                    key={cand.rank}
                    className={`bg-white rounded-2xl border transition-all p-6 shadow-sm ${
                      isTopRank
                        ? 'border-indigo-300 ring-1 ring-indigo-100'
                        : 'border-slate-200'
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-4 pb-4 border-b border-slate-100">
                      <div className="flex items-center gap-3">
                        {/* Rank Badge */}
                        <div
                          className={`flex items-center justify-center rounded-xl px-3 py-1 text-xs font-bold border ${
                            isTopRank
                              ? 'bg-amber-100 text-amber-900 border-amber-300'
                              : 'bg-slate-100 text-slate-700 border-slate-200'
                          }`}
                        >
                          {isTopRank ? 'Rank #1 (Highest)' : `Rank #${cand.rank}`}
                        </div>

                        {/* Title & Type */}
                        <div>
                          <div className="flex items-center gap-2">
                            <IconComp className="w-4 h-4 text-indigo-600" />
                            <h3 className="text-base font-bold text-slate-900">
                              {cand.label}
                            </h3>
                          </div>
                          <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                            Type key: {cand.intervention_type}
                          </p>
                        </div>
                      </div>

                      {/* Suitability Score Callout & Progress Bar */}
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                            Suitability Score
                          </div>
                          {hasScore ? (
                            <div className="flex items-center gap-2 mt-1">
                              <div className="w-24 bg-slate-100 h-2.5 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-indigo-600 rounded-full transition-all duration-300"
                                  style={{
                                    width: `${Math.min(
                                      Math.max(cand.suitability_score * 100, 0),
                                      100
                                    )}%`,
                                  }}
                                />
                              </div>
                              <span className="font-mono text-sm font-bold text-slate-900">
                                {(cand.suitability_score * 100).toFixed(1)}%
                              </span>
                            </div>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200 mt-1">
                              missing score
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Candidate Details Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
                      {/* Left: Model Explanation & Rationale */}
                      <div className="md:col-span-2 space-y-3">
                        <div>
                          <h4 className="text-xs font-bold text-slate-700 flex items-center gap-1.5 mb-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                            Algorithmic Match Rationale (Explainability NFR)
                          </h4>
                          {hasRationale ? (
                            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100 text-xs text-slate-700 leading-relaxed font-sans">
                              {cand.rationale}
                            </div>
                          ) : (
                            <div className="p-3.5 rounded-xl bg-amber-50/50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
                                missing rationale
                              </span>
                              <span>No model explanation was attached to this candidate.</span>
                            </div>
                          )}
                        </div>

                        {/* Student-Facing Preview */}
                        <div className="p-3 rounded-xl bg-indigo-50/40 border border-indigo-100 text-xs text-indigo-900">
                          <span className="font-semibold block text-[11px] uppercase tracking-wider text-indigo-600 mb-0.5">
                            Student-Facing Communication Preview (Non-Stigmatizing)
                          </span>
                          <span>"{cand.student_label}"</span>
                        </div>
                      </div>

                      {/* Right: Delivery Module & Channel Meta */}
                      <div className="bg-slate-50/60 rounded-xl p-4 border border-slate-100 space-y-3 flex flex-col justify-between">
                        <div>
                          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-2">
                            Delivery Mechanism
                          </span>
                          <div className="flex items-center gap-2 text-xs font-medium text-slate-800">
                            <IconComp className="w-4 h-4 text-indigo-600" />
                            <span>{deliveryLabel}</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
                            {cand.delivery_module === 'counselling_booking'
                              ? 'Enables booking calendar link for direct counseling appointments.'
                              : cand.delivery_module === 'resource_share'
                              ? 'Dispatches curated academic worksheets and formative exercises.'
                              : cand.delivery_module === 'peer_mentoring'
                              ? 'Facilitates peer mentor introduction via messaging channels.'
                              : 'Requires manual staff coordinator dispatch.'}
                          </p>
                        </div>

                        <div className="pt-3 border-t border-slate-200/60 text-[11px] text-slate-400">
                          Priority Priority Tier: {isTopRank ? 'Primary Choice' : `Alternative Option #${cand.rank}`}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Dushan: F33 review actions go here */}
          <div className="bg-white rounded-2xl border border-dashed border-slate-300 p-6 text-center shadow-sm">
            <h3 className="text-sm font-semibold text-slate-700">
              Staff Decision & Action Actions Slot
            </h3>
            <p className="text-xs text-slate-500 max-w-lg mx-auto mt-1">
              Decision actions (Approve, Modify Candidate, Reject with Justification) are scheduled for Feature 33.
            </p>
            {/* Dushan: F33 review actions go here */}
          </div>
        </div>
      )}
    </div>
  );
};
