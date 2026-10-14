/**
 * src/pages/StaffRecommendationsPage.tsx
 *
 * Feature 32: Staff Intervention Recommendation Panel (Component 4).
 * Ranked intervention suggestions with suitability score and explainable rationales.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Lightbulb,
  ShieldCheck,
  Filter,
  ChevronRight,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Search,
  Layers,
  Award,
  CheckCircle2,
} from 'lucide-react';
import { StaffTabs } from '../components/staff/StaffTabs';
import {
  staffRecommendationsApi,
  StaffRecommendationListItem,
} from '../api/staffRecommendations';
import { staffReviewApi } from '../api/staffReview';

const TIER_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  critical: { bg: 'bg-rose-100', text: 'text-rose-800', border: 'border-rose-200' },
  high: { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-200' },
  medium: { bg: 'bg-amber-100', text: 'text-amber-800', border: 'border-amber-200' },
  low: { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-200' },
};

const STATUS_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  proposed: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  pending: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  approved: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  modified: { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200' },
  rejected: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
};

export const StaffRecommendationsPage: React.FC = () => {
  const navigate = useNavigate();

  const [reviewTab, setReviewTab] = useState<'pending' | 'reviewed' | 'all'>('pending');
  const [pidFilter, setPidFilter] = useState<string>('');
  const [tierFilter, setTierFilter] = useState<string>('');
  const [page, setPage] = useState<number>(1);

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['staffRecommendations', reviewTab, pidFilter, tierFilter, page],
    queryFn: () =>
      staffRecommendationsApi.getRecommendations({
        review: reviewTab,
        pid: pidFilter.trim() || undefined,
        tier: tierFilter || undefined,
        page,
        page_size: 20,
      }),
  });

  const { data: stats } = useQuery({
    queryKey: ['staffReviewStats'],
    queryFn: staffReviewApi.getReviewStats,
  });

  const recommendations = data?.items || [];
  const totalCount = data?.total_count || 0;
  const totalPages = data?.total_pages || 1;

  const handleRowClick = (rec: StaffRecommendationListItem) => {
    navigate(`/staff/recommendations/${encodeURIComponent(rec.recommendation_id)}`);
  };

  const renderTierChip = (tier: string | null) => {
    if (!tier) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500">
          Unassessed
        </span>
      );
    }
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
        {tier}
      </span>
    );
  };

  const renderStatusChip = (statusVal: string) => {
    const key = statusVal.toLowerCase();
    const style = STATUS_STYLES[key] || {
      bg: 'bg-slate-50',
      text: 'text-slate-600',
      border: 'border-slate-200',
    };
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium uppercase tracking-wider border ${style.bg} ${style.text} ${style.border}`}
      >
        {statusVal}
      </span>
    );
  };

  const getErrorMessage = (err: any): string => {
    return (
      err?.response?.data?.detail ||
      err?.message ||
      'Unable to load intervention recommendations.'
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header Banner */}
      <div className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Student Support & Analytics
              </h1>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                <ShieldCheck className="w-3.5 h-3.5" />
                Counsellor workspace
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Component 4 Adaptive Intervention Recommendation Panel — Cause-matched intervention candidates ranked with predicted suitability scores.
            </p>
          </div>
          <div className="text-xs text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 flex items-center gap-1.5">
            <Lightbulb className="w-4 h-4 text-indigo-600" />
            Decision-support only • Human review required
          </div>
        </div>

        {/* Staff Workspace Navigation Tabs */}
        <StaffTabs />
      </div>

      {/* Review State Segmented Tabs */}
      <div className="flex items-center gap-2 mb-4 border-b border-slate-200">
        <button
          type="button"
          onClick={() => {
            setReviewTab('pending');
            setPage(1);
          }}
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
            reviewTab === 'pending'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Pending Review
        </button>
        <button
          type="button"
          onClick={() => {
            setReviewTab('reviewed');
            setPage(1);
          }}
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
            reviewTab === 'reviewed'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Reviewed / Decided
        </button>
        <button
          type="button"
          onClick={() => {
            setReviewTab('all');
            setPage(1);
          }}
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition ${
            reviewTab === 'all'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          All Recommendations
        </button>
      </div>

      {/* Review Rate & Human-in-the-Loop Coverage Card */}
      {stats && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-900">
                  Human-in-the-Loop Review Rate
                </span>
                <span className="text-xs font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                  {(stats.review_rate * 100).toFixed(1)}%
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                C4 Human Control NFR: 100% of candidate recommendations require authorized review before student action.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <div className="text-center px-3 py-1 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-[10px] text-slate-400 block font-semibold">TOTAL</span>
              <span className="font-bold text-slate-800 font-mono">{stats.total}</span>
            </div>
            <div className="text-center px-3 py-1 bg-amber-50 rounded-lg border border-amber-100">
              <span className="text-[10px] text-amber-600 block font-semibold">PENDING</span>
              <span className="font-bold text-amber-800 font-mono">{stats.pending}</span>
            </div>
            <div className="text-center px-3 py-1 bg-emerald-50 rounded-lg border border-emerald-100">
              <span className="text-[10px] text-emerald-600 block font-semibold">APPROVED</span>
              <span className="font-bold text-emerald-800 font-mono">{stats.approved}</span>
            </div>
            <div className="text-center px-3 py-1 bg-sky-50 rounded-lg border border-sky-100">
              <span className="text-[10px] text-sky-600 block font-semibold">MODIFIED</span>
              <span className="font-bold text-sky-800 font-mono">{stats.modified}</span>
            </div>
            <div className="text-center px-3 py-1 bg-rose-50 rounded-lg border border-rose-100">
              <span className="text-[10px] text-rose-600 block font-semibold">REJECTED</span>
              <span className="font-bold text-rose-800 font-mono">{stats.rejected}</span>
            </div>
          </div>
        </div>
      )}

      {/* Filters Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-slate-600 text-sm font-medium mr-1">
              <Filter className="w-4 h-4 text-indigo-600" />
              <span>Filters:</span>
            </div>

            {/* PID Filter */}
            <div className="relative min-w-[200px]">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter by PID (e.g. STU_...)"
                value={pidFilter}
                onChange={(e) => {
                  setPidFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full text-sm border-slate-200 rounded-lg pl-9 pr-3 py-2 bg-slate-50/50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
              />
            </div>

            {/* Risk Tier Filter */}
            <div className="min-w-[150px]">
              <select
                id="recommendation-tier-filter"
                value={tierFilter}
                onChange={(e) => {
                  setTierFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full text-sm border-slate-200 rounded-lg px-3 py-2 bg-slate-50/50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
              >
                <option value="">All Risk Tiers</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            {(pidFilter || tierFilter) && (
              <button
                type="button"
                onClick={() => {
                  setPidFilter('');
                  setTierFilter('');
                  setPage(1);
                }}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium px-2 py-1"
              >
                Clear filters
              </button>
            )}
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>
              Showing <strong className="text-slate-800">{recommendations.length}</strong> of{' '}
              <strong className="text-slate-800">{totalCount}</strong> batches
            </span>
            <button
              type="button"
              onClick={() => refetch()}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              title="Refresh list"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content Area */}
      {isLoading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-600">
            Loading ranked intervention recommendations...
          </p>
        </div>
      ) : isError ? (
        <div className="bg-rose-50 rounded-2xl border border-rose-200 p-6 text-rose-800 shadow-sm">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-sm">Failed to load recommendations</h3>
              <p className="text-xs text-rose-700 mt-1">{getErrorMessage(error)}</p>
            </div>
          </div>
        </div>
      ) : recommendations.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <Lightbulb className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">
            No recommendations in this view
          </h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
            {reviewTab === 'pending'
              ? 'There are currently no pending intervention recommendations requiring staff review.'
              : 'No intervention recommendations matched the current filter criteria.'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50/75 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-3.5">
                    Student PID
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Week
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Risk Tier
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Top Ranked Intervention (Rank #1)
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Suitability Score
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Candidates
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Status
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-right">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recommendations.map((rec) => (
                  <tr
                    key={rec.recommendation_id}
                    onClick={() => handleRowClick(rec)}
                    className="hover:bg-indigo-50/40 cursor-pointer transition group"
                  >
                    <td className="px-6 py-4 font-mono font-medium text-slate-800 text-xs">
                      <span className="bg-slate-100 px-2 py-1 rounded text-slate-700 group-hover:bg-white group-hover:text-indigo-700 transition">
                        {rec.pid}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-600 text-xs">
                      W{rec.week_index}
                    </td>
                    <td className="px-6 py-4">
                      {renderTierChip(rec.risk_tier)}
                    </td>
                    <td className="px-6 py-4">
                      {rec.top_candidate ? (
                        <div className="flex items-center gap-1.5 text-slate-800 font-medium text-xs">
                          <Award className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
                          <span>{rec.top_candidate.label}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400 text-xs">No candidates</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {rec.top_candidate ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-slate-100 h-2 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-indigo-600 rounded-full"
                              style={{
                                width: `${Math.min(
                                  Math.max(rec.top_candidate.suitability_score * 100, 0),
                                  100
                                )}%`,
                              }}
                            />
                          </div>
                          <span className="font-mono text-xs text-slate-700 font-semibold">
                            {(rec.top_candidate.suitability_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-xs">
                      <span className="inline-flex items-center gap-1 text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                        <Layers className="w-3 h-3 text-slate-400" />
                        {rec.candidate_count} {rec.candidate_count === 1 ? 'option' : 'options'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {renderStatusChip(rec.status)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="inline-flex items-center text-xs font-semibold text-indigo-600 group-hover:text-indigo-800 transition">
                        Inspect
                        <ChevronRight className="w-4 h-4 ml-0.5 group-hover:translate-x-0.5 transition-transform" />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          {totalPages > 1 && (
            <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
              <div>
                Page <strong className="text-slate-900">{page}</strong> of{' '}
                <strong className="text-slate-900">{totalPages}</strong>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
