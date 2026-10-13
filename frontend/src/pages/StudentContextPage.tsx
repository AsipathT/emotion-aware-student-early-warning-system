/**
 * src/pages/StudentContextPage.tsx
 *
 * Feature 31: Comprehensive Multi-Modal Student Context Summary (Component 4).
 * Combines C1 (affective), C2 (engagement trajectory), C3 (dropout risk + causal modality),
 * behavior clickstream, and intervention history.
 */

import React from 'react';
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  Sparkles,
  Compass,
  Activity,
  History,
  Clock,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Info,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { StaffTabs } from '../components/staff/StaffTabs';
import { IdentityRevealModal } from '../components/privacy/IdentityRevealModal';
import { staffStudentsApi, StudentContextResponse } from '../api/staffStudents';

const EMOTION_COLORS: Record<string, string> = {
  frustration: '#f43f5e', // rose-500
  anxiety: '#f97316', // orange-500
  confusion: '#eab308', // yellow-500
  boredom: '#64748b', // slate-500
  motivation_erosion: '#8b5cf6', // purple-500
};

const EMOTION_LABELS: Record<string, string> = {
  frustration: 'Frustration',
  anxiety: 'Anxiety',
  confusion: 'Confusion',
  boredom: 'Boredom',
  motivation_erosion: 'Motivation Erosion',
};

const TIER_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  critical: { bg: 'bg-rose-100', text: 'text-rose-800', border: 'border-rose-200' },
  high: { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-200' },
  medium: { bg: 'bg-amber-100', text: 'text-amber-800', border: 'border-amber-200' },
  low: { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-200' },
};

const TRAJECTORY_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  improving: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  stable: { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200' },
  fluctuating: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  declining: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  disengaged: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
};

export const StudentContextPage: React.FC = () => {
  const { pid } = useParams<{ pid: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const courseId = searchParams.get('course_id') || '';

  const {
    data: context,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<StudentContextResponse>({
    queryKey: ['studentContext', pid, courseId],
    queryFn: () => staffStudentsApi.getStudentContext(pid!, courseId),
    enabled: Boolean(pid && courseId),
  });

  const getErrorMessage = (err: any): string => {
    return (
      err?.response?.data?.detail ||
      err?.message ||
      'Failed to load student context profile.'
    );
  };

  if (!courseId) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <StaffTabs />
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 text-amber-800 mt-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-sm">Course Identifier Missing</h3>
              <p className="text-xs text-amber-700 mt-1">
                Please select a course to view the student context summary.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/staff/students')}
            className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to student list
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Navigation & Breadcrumb */}
      <div className="mb-6">
        <div className="flex items-center justify-between gap-4 mb-3">
          <Link
            to="/staff/students"
            className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Student Triage List
          </Link>
          <div className="text-xs text-slate-500 bg-slate-100 px-3 py-1 rounded-lg border border-slate-200 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
            Pseudonymous Record • Strictly Audited
          </div>
        </div>

        {/* Header Profile Banner */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Student Context Profile
                </span>
                <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                  PID: {pid}
                </span>
                <span className="px-2.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                  Course: {courseId}
                </span>
              </div>
              <h1 className="text-xl font-bold text-slate-900 mt-1">
                Component 4 Unified Early Warning Context
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Multi-modal synthesis of Affective State (C1), Engagement Trajectory (C2), and Dropout Risk (C3).
              </p>
            </div>

            {/* Niduka's Reusable Identity Reveal Component */}
            {pid && (
              <div className="flex items-center">
                <IdentityRevealModal
                  pid={pid}
                  buttonLabel="Reveal Identity"
                  size="sm"
                />
              </div>
            )}
          </div>
        </div>

        {/* Staff Navigation Tabs */}
        <StaffTabs />
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="bg-white rounded-2xl border border-slate-200 p-16 text-center shadow-sm">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-600">
            Synthesizing student context across C1, C2, and C3 models...
          </p>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div className="bg-rose-50 rounded-2xl border border-rose-200 p-6 text-rose-800 shadow-sm">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-sm">Context Assembly Error</h3>
              <p className="text-xs text-rose-700 mt-1">{getErrorMessage(error)}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 text-xs font-semibold text-rose-700 hover:text-rose-900 underline"
          >
            Retry assembly
          </button>
        </div>
      )}

      {/* Main Content when loaded */}
      {context && (
        <div className="space-y-6">
          {/* Summary Box with plain-language bullets & Data Freshness */}
          <div className="bg-gradient-to-br from-indigo-50/60 via-white to-slate-50 rounded-2xl border border-indigo-100 p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-600" />
                <h2 className="text-base font-bold text-slate-900">
                  Synthesized Context Summary
                </h2>
              </div>
              <span className="text-xs font-semibold text-indigo-700 bg-indigo-100/70 px-3 py-1 rounded-full">
                Common Reference: Week {context.latest_common_week}
              </span>
            </div>

            {/* Template-driven plain-language bullets */}
            <div className="space-y-2 mb-5">
              {context.summary_lines.map((line, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-sm text-slate-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-2 flex-shrink-0" />
                  <span>{line}</span>
                </div>
              ))}
            </div>

            {/* Data Freshness Warning Chips */}
            <div className="border-t border-indigo-100/80 pt-4 flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-slate-500 mr-1 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                Data Freshness:
              </span>
              {context.data_freshness.lagging_sources.length === 0 ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="w-3 h-3" />
                  All ML components synchronized at Week {context.data_freshness.max_observed_week}
                </span>
              ) : (
                context.data_freshness.lagging_sources.map((ls, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200"
                  >
                    <AlertTriangle className="w-3 h-3 text-amber-600" />
                    {ls.source} lags by {ls.lag_weeks} {ls.lag_weeks === 1 ? 'week' : 'weeks'} (W{ls.week ?? 0})
                  </span>
                ))
              )}
            </div>
          </div>

          {/* 3 Core Cards: C1, C2, C3 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Card 1: C1 Affective State */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-xl bg-purple-50 text-purple-600">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-900 text-sm">
                        Affective State (C1)
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        {context.c1.latest
                          ? `Week ${context.c1.latest.week_index} Assessment`
                          : 'No affective records'}
                      </p>
                    </div>
                  </div>
                  {context.c1.latest && (
                    <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 capitalize">
                      {context.c1.latest.stress_label.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>

                {context.c1.latest ? (
                  <div className="space-y-4">
                    {/* Dominant Class Callout */}
                    <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
                      <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                        Dominant Distress Class
                      </div>
                      <div className="flex items-baseline justify-between mt-1">
                        <span className="text-sm font-bold text-slate-800 capitalize">
                          {context.c1.latest.dominant_class.replace(/_/g, ' ')}
                        </span>
                        <span className="text-xs font-mono font-semibold text-slate-600">
                          {(context.c1.latest.dominant_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    {/* Emotion Score Progress Bars */}
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-slate-600">
                        Distress Class Breakdown
                      </div>
                      {Object.entries(context.c1.latest.emotion_scores).map(([cls, val]) => (
                        <div key={cls} className="space-y-1">
                          <div className="flex justify-between text-xs text-slate-600">
                            <span>{EMOTION_LABELS[cls] || cls}</span>
                            <span className="font-mono text-slate-500">
                              {(val * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-300"
                              style={{
                                width: `${Math.min(Math.max(val * 100, 0), 100)}%`,
                                backgroundColor: EMOTION_COLORS[cls] || '#6366f1',
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Historical class progression */}
                    {context.c1.history.length > 1 && (
                      <div className="pt-2 border-t border-slate-100">
                        <div className="text-[11px] font-semibold text-slate-500 mb-2">
                          Recent History (Dominant)
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {context.c1.history.map((h, i) => (
                            <span
                              key={i}
                              className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600"
                            >
                              W{h.week_index}: {h.dominant_class}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-6 text-center">
                    No affective state data available for this course.
                  </p>
                )}
              </div>

              {/* Action Link to Full Affective Explainability Detail */}
              <div className="mt-6 pt-3 border-t border-slate-100">
                <Link
                  to={`/staff/affective/${encodeURIComponent(pid!)}?course_id=${encodeURIComponent(
                    courseId
                  )}`}
                  className="w-full inline-flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-xs font-semibold text-indigo-600 bg-indigo-50/60 hover:bg-indigo-100/70 transition"
                >
                  View full C1 affective explainability
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>

            {/* Card 2: C2 Engagement Trajectory */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-xl bg-sky-50 text-sky-600">
                      <Compass className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-900 text-sm">
                        Engagement Trajectory (C2)
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        {context.c2.latest
                          ? `Week ${context.c2.latest.week_index} Assessment`
                          : 'No trajectory records'}
                      </p>
                    </div>
                  </div>
                  {context.c2.latest && (
                    <span
                      className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border capitalize ${
                        TRAJECTORY_STYLES[context.c2.latest.trajectory_label.toLowerCase()]?.bg ||
                        'bg-slate-100'
                      } ${
                        TRAJECTORY_STYLES[context.c2.latest.trajectory_label.toLowerCase()]?.text ||
                        'text-slate-700'
                      } ${
                        TRAJECTORY_STYLES[context.c2.latest.trajectory_label.toLowerCase()]?.border ||
                        'border-slate-200'
                      }`}
                    >
                      {context.c2.latest.trajectory_label.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>

                {context.c2.latest ? (
                  <div className="space-y-4">
                    {/* Contributing Indicators Chips */}
                    <div>
                      <div className="text-xs font-semibold text-slate-600 mb-2">
                        Contributing Indicators (Model Transparency)
                      </div>
                      {context.c2.latest.contributing_indicators.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {context.c2.latest.contributing_indicators.map((ind, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200"
                            >
                              {ind}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-400">
                          No contributing indicators flagged.
                        </p>
                      )}
                    </div>

                    {/* Small Timeline of Trajectory Labels */}
                    {context.c2.history.length > 0 && (
                      <div className="pt-2 border-t border-slate-100">
                        <div className="text-xs font-semibold text-slate-600 mb-2">
                          Trajectory History
                        </div>
                        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                          {context.c2.history.map((h, i) => (
                            <div
                              key={i}
                              className="text-center px-2 py-1 bg-slate-50 rounded-lg border border-slate-200 flex-shrink-0"
                            >
                              <div className="text-[10px] text-slate-400 font-medium">
                                W{h.week_index}
                              </div>
                              <div className="text-[11px] font-semibold text-slate-700 capitalize">
                                {h.trajectory_label.replace(/_/g, ' ')}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Clickstream Behavior Summary */}
                    {context.behaviour.history.length > 0 && (
                      <div className="pt-2 border-t border-slate-100">
                        <div className="text-xs font-semibold text-slate-600 mb-2">
                          Latest Behavioral Clickstream (W{context.behaviour.history[0].week_index})
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                            <span className="text-[10px] text-slate-400 block">Logins</span>
                            <span className="font-semibold text-slate-700">
                              {context.behaviour.history[0].login_count} sessions
                            </span>
                          </div>
                          <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                            <span className="text-[10px] text-slate-400 block">Session Time</span>
                            <span className="font-semibold text-slate-700">
                              {context.behaviour.history[0].session_minutes} min
                            </span>
                          </div>
                          <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                            <span className="text-[10px] text-slate-400 block">Clicks</span>
                            <span className="font-semibold text-slate-700">
                              {context.behaviour.history[0].clicks} clicks
                            </span>
                          </div>
                          <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                            <span className="text-[10px] text-slate-400 block">Submission Delay</span>
                            <span className="font-semibold text-slate-700">
                              {context.behaviour.history[0].avg_submission_delay_hours} hrs
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-6 text-center">
                    No trajectory analytics available for this course.
                  </p>
                )}
              </div>
            </div>

            {/* Card 3: C3 Dropout Risk & Causal Modality Vector */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-xl bg-rose-50 text-rose-600">
                      <Activity className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-900 text-sm">
                        Dropout Risk & Causality (C3)
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        {context.c3.latest
                          ? `Week ${context.c3.latest.week_index} Assessment`
                          : 'No risk assessment records'}
                      </p>
                    </div>
                  </div>
                  {context.c3.latest && (
                    <span
                      className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border uppercase tracking-wider ${
                        TIER_STYLES[context.c3.latest.risk_tier.toLowerCase()]?.bg ||
                        'bg-slate-100'
                      } ${
                        TIER_STYLES[context.c3.latest.risk_tier.toLowerCase()]?.text ||
                        'text-slate-700'
                      } ${
                        TIER_STYLES[context.c3.latest.risk_tier.toLowerCase()]?.border ||
                        'border-slate-200'
                      }`}
                    >
                      {context.c3.latest.risk_tier}
                    </span>
                  )}
                </div>

                {context.c3.latest ? (
                  <div className="space-y-4">
                    {/* Risk Score Highlight */}
                    <div className="flex items-baseline justify-between bg-slate-50 rounded-xl p-3 border border-slate-100">
                      <span className="text-xs font-semibold text-slate-600">
                        Predicted Dropout Probability
                      </span>
                      <span className="text-lg font-bold font-mono text-slate-900">
                        {(context.c3.latest.risk_score * 100).toFixed(1)}%
                      </span>
                    </div>

                    {/* Dominant Modality Sentence */}
                    <div className="p-3 bg-indigo-50/70 border border-indigo-100 rounded-xl text-xs text-indigo-900 leading-relaxed">
                      <strong>Dominant driver: </strong>
                      <span className="capitalize">{context.c3.latest.dominant_modality}</span> signals
                      contribute most (
                      {(context.c3.latest.dominant_modality_value * 100).toFixed(1)}%) to the student's risk profile.
                    </div>

                    {/* Stacked Modality Contributions Bar */}
                    <div>
                      <div className="flex items-center justify-between text-xs text-slate-600 mb-1.5">
                        <span className="font-semibold">Causal Modality Breakdown</span>
                        <span className="text-[11px] text-slate-400">Sum = 100%</span>
                      </div>
                      <div className="w-full h-3 rounded-full overflow-hidden flex bg-slate-100">
                        <div
                          style={{
                            width: `${(context.c3.latest.modality_contributions.affective * 100).toFixed(1)}%`,
                          }}
                          className="bg-purple-500 h-full"
                          title={`Affective: ${(context.c3.latest.modality_contributions.affective * 100).toFixed(1)}%`}
                        />
                        <div
                          style={{
                            width: `${(context.c3.latest.modality_contributions.behavioral * 100).toFixed(1)}%`,
                          }}
                          className="bg-sky-500 h-full"
                          title={`Behavioral: ${(context.c3.latest.modality_contributions.behavioral * 100).toFixed(1)}%`}
                        />
                        <div
                          style={{
                            width: `${(context.c3.latest.modality_contributions.academic * 100).toFixed(1)}%`,
                          }}
                          className="bg-amber-500 h-full"
                          title={`Academic: ${(context.c3.latest.modality_contributions.academic * 100).toFixed(1)}%`}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-slate-500 mt-1.5">
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-purple-500" />
                          Affective ({(context.c3.latest.modality_contributions.affective * 100).toFixed(0)}%)
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-sky-500" />
                          Behavioral ({(context.c3.latest.modality_contributions.behavioral * 100).toFixed(0)}%)
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-amber-500" />
                          Academic ({(context.c3.latest.modality_contributions.academic * 100).toFixed(0)}%)
                        </span>
                      </div>
                    </div>

                    {/* Recharts Risk Score Line Chart */}
                    {context.c3.history.length > 1 && (
                      <div className="pt-2 border-t border-slate-100">
                        <div className="text-xs font-semibold text-slate-600 mb-2">
                          Risk Trend Across Weeks
                        </div>
                        <div className="h-28 w-full">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart
                              data={[...context.c3.history].reverse().map((h) => ({
                                week: `W${h.week_index}`,
                                risk: Math.round(h.risk_score * 100),
                              }))}
                              margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                              <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                              <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                              <Tooltip
                                formatter={(val: any) => [`${val}%`, 'Risk Score']}
                                contentStyle={{
                                  fontSize: '11px',
                                  borderRadius: '8px',
                                  borderColor: '#e2e8f0',
                                }}
                              />
                              <Line
                                type="monotone"
                                dataKey="risk"
                                stroke="#f43f5e"
                                strokeWidth={2}
                                dot={{ r: 3, fill: '#f43f5e' }}
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 py-6 text-center">
                    No risk assessment analytics available for this course.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Intervention History Timeline */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100">
              <History className="w-5 h-5 text-indigo-600" />
              <div>
                <h3 className="font-bold text-slate-900 text-sm">
                  Intervention History & Prior Outcomes
                </h3>
                <p className="text-xs text-slate-500">
                  Institutional record of support actions and follow-up resolutions.
                </p>
              </div>
            </div>

            {context.interventions.history.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <Info className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                <p className="text-xs">No prior interventions recorded for this student.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {context.interventions.history.map((inv, idx) => (
                  <div
                    key={inv.id || idx}
                    className="p-4 rounded-xl border border-slate-100 bg-slate-50/50 flex flex-wrap items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800 capitalize">
                          {inv.intervention_type.replace(/_/g, ' ')}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-200 text-slate-700 capitalize">
                          {inv.status}
                        </span>
                        {inv.channel && (
                          <span className="text-slate-400">via {inv.channel}</span>
                        )}
                      </div>
                      {inv.notes && (
                        <p className="text-slate-600 text-xs italic">
                          "{inv.notes}"
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-slate-500">
                      {inv.outcome_metric && (
                        <span>
                          Metric: <strong>{inv.outcome_metric}</strong> (
                          {inv.change_observed !== undefined ? inv.change_observed : 0})
                        </span>
                      )}
                      <span>
                        {inv.applied_at || inv.recommended_at || inv.recorded_at || 'Recent'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
