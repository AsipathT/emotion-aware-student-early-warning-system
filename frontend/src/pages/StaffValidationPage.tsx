/**
 * src/pages/StaffValidationPage.tsx
 *
 * Feature 36: Counsellor Ground-Truth Validation Workspace (Component 1 & Component 4).
 * Provides blind C1 distress confirmation and C4 recommendation appropriateness ratings.
 */

import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Brain,
  CheckSquare,
  Sparkles,
  Download,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Lock,
  Star,
  ArrowRight,
  MessageSquare,
  Filter,
  BarChart2,
  ShieldCheck,
  Award,
} from 'lucide-react';
import { StaffTabs } from '../components/staff/StaffTabs';
import {
  staffValidationApi,
  C1DistressLabel,
  C1QueueItemResponse,
  C1LabelCreateResponse,
  C4QueueItemResponse,
} from '../api/staffValidation';
import { useAuth } from '../hooks/useAuth';

const C1_LABEL_OPTIONS: { value: C1DistressLabel; label: string; description: string }[] = [
  { value: 'exam_anxiety', label: 'Exam Anxiety', description: 'Acute apprehension, panic, or distress regarding exams/quizzes.' },
  { value: 'conceptual_confusion', label: 'Conceptual Confusion', description: 'Struggling with core syllabus concepts or course materials.' },
  { value: 'academic_helplessness', label: 'Academic Helplessness', description: 'Feelings of inability to succeed or perceived lack of agency.' },
  { value: 'course_frustration', label: 'Course Frustration', description: 'Irritation with workload, deadlines, assignments, or pacing.' },
  { value: 'motivation_erosion', label: 'Motivation Erosion', description: 'Apathy, declining interest, fatigue, or disengagement.' },
  { value: 'none', label: 'No Observable Distress', description: 'Neutral, constructive, or typical academic inquiry.' },
];

export const StaffValidationPage: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  // Workspace sub-tabs
  const [activeTab, setActiveTab] = useState<'c1' | 'c4'>('c1');

  // ── C1 Labelling State ──────────────────────────────────────────────────────
  const [selectedCourseFilter, setSelectedCourseFilter] = useState<string>('');
  const [currentC1Index, setCurrentC1Index] = useState<number>(0);
  const [c1Choice, setC1Choice] = useState<C1DistressLabel>('none');
  const [c1Confidence, setC1Confidence] = useState<number>(2);
  const [c1RevealResult, setC1RevealResult] = useState<C1LabelCreateResponse | null>(null);
  const [c1Error, setC1Error] = useState<string | null>(null);

  // ── C4 Rating State ────────────────────────────────────────────────────────
  const [currentC4Index, setCurrentC4Index] = useState<number>(0);
  const [c4Appropriateness, setC4Appropriateness] = useState<number>(4);
  const [suitableRanks, setSuitableRanks] = useState<number[]>([1]);
  const [top1Acceptable, setTop1Acceptable] = useState<boolean>(true);
  const [c4Comment, setC4Comment] = useState<string>('');
  const [c4Error, setC4Error] = useState<string | null>(null);
  const [c4SuccessMsg, setC4SuccessMsg] = useState<string | null>(null);

  // ── Export State ───────────────────────────────────────────────────────────
  const [isExporting, setIsExporting] = useState<boolean>(false);

  // ── Queries ────────────────────────────────────────────────────────────────
  const {
    data: c1Queue = [],
    isLoading: isC1QueueLoading,
    refetch: refetchC1Queue,
  } = useQuery({
    queryKey: ['validation-c1-queue', selectedCourseFilter],
    queryFn: () => staffValidationApi.getC1Queue({ course_id: selectedCourseFilter || undefined, limit: 20 }),
  });

  const {
    data: c1Summary,
    refetch: refetchC1Summary,
  } = useQuery({
    queryKey: ['validation-c1-summary', selectedCourseFilter],
    queryFn: () => staffValidationApi.getC1Summary(selectedCourseFilter || undefined),
  });

  const {
    data: c4Queue = [],
    isLoading: isC4QueueLoading,
    refetch: refetchC4Queue,
  } = useQuery({
    queryKey: ['validation-c4-queue'],
    queryFn: () => staffValidationApi.getC4Queue(20),
  });

  const {
    data: c4Summary,
    refetch: refetchC4Summary,
  } = useQuery({
    queryKey: ['validation-c4-summary'],
    queryFn: () => staffValidationApi.getC4Summary(),
  });

  // ── C1 Submit Mutation ──────────────────────────────────────────────────────
  const c1Mutation = useMutation({
    mutationFn: staffValidationApi.submitC1Label,
    onSuccess: (data) => {
      setC1RevealResult(data);
      setC1Error(null);
      refetchC1Summary();
    },
    onError: (err: any) => {
      setC1Error(err?.response?.data?.detail || 'Failed to record C1 validation label.');
    },
  });

  // ── C4 Submit Mutation ──────────────────────────────────────────────────────
  const c4Mutation = useMutation({
    mutationFn: staffValidationApi.submitC4Rating,
    onSuccess: () => {
      setC4SuccessMsg('Appropriateness rating recorded successfully.');
      setC4Error(null);
      refetchC4Summary();
      refetchC4Queue();
      // Reset form
      setC4Comment('');
      setSuitableRanks([1]);
      setC4Appropriateness(4);
      setTop1Acceptable(true);
      setCurrentC4Index(0);
    },
    onError: (err: any) => {
      setC4Error(err?.response?.data?.detail || 'Failed to record C4 recommendation rating.');
    },
  });

  // Current active queue items
  const activeC1Item: C1QueueItemResponse | undefined = c1Queue[currentC1Index];
  const activeC4Item: C4QueueItemResponse | undefined = c4Queue[currentC4Index];

  // ── C1 Handlers ─────────────────────────────────────────────────────────────
  const handleC1Submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeC1Item) return;
    setC1Error(null);
    c1Mutation.mutate({
      pid: activeC1Item.pid,
      course_id: activeC1Item.course_id,
      week_index: activeC1Item.week_index,
      counsellor_label: c1Choice,
      confidence: c1Confidence,
    });
  };

  const handleNextC1 = () => {
    setC1RevealResult(null);
    setC1Choice('none');
    setC1Confidence(2);
    refetchC1Queue();
    setCurrentC1Index((prev) => (prev + 1 < c1Queue.length ? prev + 1 : 0));
  };

  // ── C4 Handlers ─────────────────────────────────────────────────────────────
  const toggleRankSuitability = (rank: number) => {
    setSuitableRanks((prev) =>
      prev.includes(rank) ? prev.filter((r) => r !== rank) : [...prev, rank].sort()
    );
  };

  const handleC4Submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeC4Item) return;
    setC4Error(null);
    setC4SuccessMsg(null);
    c4Mutation.mutate({
      recommendation_id: activeC4Item.recommendation_id,
      appropriateness: c4Appropriateness,
      suitable_ranks: suitableRanks,
      top1_acceptable: top1Acceptable,
      comment: c4Comment.trim() ? c4Comment.trim() : null,
    });
  };

  // ── Admin Export ────────────────────────────────────────────────────────────
  const handleExport = async () => {
    setIsExporting(true);
    try {
      const data = await staffValidationApi.exportValidationData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `validation-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to download validation export.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Navigation tabs */}
      <StaffTabs />

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-2xl bg-indigo-50 text-indigo-600">
              <CheckSquare className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Counsellor Validation Tools
              </h1>
              <p className="text-sm text-slate-500">
                Independent expert ground-truth validation for Affective Detection (C1) and Adaptive Interventions (C4).
              </p>
            </div>
          </div>
        </div>

        {isAdmin && (
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition disabled:opacity-50"
          >
            {isExporting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            <span>Download Research Export</span>
          </button>
        )}
      </div>

      {/* Primary Sub-Tab Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6 border-b border-slate-200 pb-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('c1')}
            className={`flex items-center gap-2 pb-2 px-2 text-sm font-semibold transition border-b-2 ${
              activeTab === 'c1'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Brain className="w-4 h-4" />
            <span>C1 Distress Labelling</span>
            {c1Queue.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-100 text-indigo-700 font-bold">
                {c1Queue.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('c4')}
            className={`flex items-center gap-2 pb-2 px-2 text-sm font-semibold transition border-b-2 ${
              activeTab === 'c4'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Award className="w-4 h-4" />
            <span>C4 Recommendation Rating</span>
            {c4Queue.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-100 text-indigo-700 font-bold">
                {c4Queue.length}
              </span>
            )}
          </button>
        </div>

        {activeTab === 'c1' && (
          <div className="flex items-center gap-2 pb-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Filter by Course ID..."
              value={selectedCourseFilter}
              onChange={(e) => {
                setSelectedCourseFilter(e.target.value);
                setCurrentC1Index(0);
                setC1RevealResult(null);
              }}
              className="text-xs px-3 py-1.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 w-44 bg-white"
            />
          </div>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          TAB 1: C1 DISTRESS LABELLING
          ═══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'c1' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Labelling Pane (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            {isC1QueueLoading ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400">
                <Loader2 className="w-8 h-8 animate-spin mx-auto text-indigo-600 mb-2" />
                <span className="text-sm">Loading blind observation queue...</span>
              </div>
            ) : !activeC1Item ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
                <h3 className="text-base font-bold text-slate-900 mb-1">
                  All Items Validated
                </h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  You have labelled all available weekly affective observations in the active cohort. Review aggregate statistics in the summary panel.
                </p>
              </div>
            ) : (
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-5">
                {/* Header Information */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100">
                        {activeC1Item.pid}
                      </span>
                      <span className="text-xs font-semibold text-slate-700">
                        {activeC1Item.course_id}
                      </span>
                      <span className="text-xs text-slate-400">
                        • Week {activeC1Item.week_index + 1}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500">
                      Blind review item {currentC1Index + 1} of {c1Queue.length}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                      <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
                      Blind Review Active
                    </span>
                  </div>
                </div>

                {/* Evidence Panel: Scrubbed Messages */}
                <div>
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-indigo-600" />
                    Student Communication Evidence ({activeC1Item.message_count} messages)
                  </h4>

                  {activeC1Item.messages.length === 0 ? (
                    <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-400">
                      No textual interaction messages recorded for this week.
                    </div>
                  ) : (
                    <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                      {activeC1Item.messages.map((m) => (
                        <div
                          key={m.message_id}
                          className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-800 space-y-1"
                        >
                          <div className="flex items-center justify-between text-[11px] text-slate-400">
                            <span className="uppercase font-semibold text-slate-600 bg-white px-1.5 py-0.5 rounded border border-slate-200">
                              {m.source_type}
                            </span>
                            <span>{new Date(m.timestamp).toLocaleDateString()}</span>
                          </div>
                          <p className="text-xs text-slate-700 leading-relaxed italic">
                            "{m.clean_text}"
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Error Banner */}
                {c1Error && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                    <span>{c1Error}</span>
                  </div>
                )}

                {/* Side-by-side Reveal State upon Submission */}
                {c1RevealResult ? (
                  <div className="p-5 rounded-2xl bg-indigo-50/50 border border-indigo-100 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-indigo-600" />
                        <h4 className="text-sm font-bold text-slate-900">
                          Model Prediction Revealed
                        </h4>
                      </div>

                      {c1RevealResult.agreement ? (
                        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          Consensus: Agreed
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
                          <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                          Discrepancy
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-xs">
                      <div className="p-3 rounded-xl bg-white border border-slate-200">
                        <span className="text-slate-400 block mb-1">Your Expert Label</span>
                        <span className="font-bold text-slate-900 text-sm">
                          {c1RevealResult.counsellor_label}
                        </span>
                        <span className="text-[11px] text-slate-500 block mt-0.5">
                          Confidence: {c1RevealResult.confidence}/3
                        </span>
                      </div>

                      <div className="p-3 rounded-xl bg-white border border-slate-200">
                        <span className="text-slate-400 block mb-1">C1 Model Top Class</span>
                        <span className="font-bold text-indigo-600 text-sm">
                          {c1RevealResult.model_top_class}
                        </span>
                        <span className="text-[11px] text-slate-500 block mt-0.5">
                          Confidence Score: {(c1RevealResult.model_top_score * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={handleNextC1}
                      className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs flex items-center justify-center gap-2 transition shadow-sm"
                    >
                      <span>Proceed to Next Item</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  /* Labelling Form */
                  <form onSubmit={handleC1Submit} className="space-y-4 pt-2">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                        Select Observed Academic Distress Class:
                      </label>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        {C1_LABEL_OPTIONS.map((opt) => {
                          const isSelected = c1Choice === opt.value;
                          return (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => setC1Choice(opt.value)}
                              className={`p-3 rounded-xl border text-left transition ${
                                isSelected
                                  ? 'bg-indigo-50 border-indigo-500 ring-2 ring-indigo-500/20'
                                  : 'bg-white border-slate-200 hover:bg-slate-50'
                              }`}
                            >
                              <div className="font-semibold text-xs text-slate-900">
                                {opt.label}
                              </div>
                              <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                                {opt.description}
                              </p>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Confidence Selector */}
                    <div>
                      <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                        Rating Confidence:
                      </label>
                      <div className="flex items-center gap-2">
                        {[
                          { val: 1, label: '1 - Low Certainty' },
                          { val: 2, label: '2 - Moderate' },
                          { val: 3, label: '3 - High Certainty' },
                        ].map((c) => (
                          <button
                            key={c.val}
                            type="button"
                            onClick={() => setC1Confidence(c.val)}
                            className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition ${
                              c1Confidence === c.val
                                ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                            }`}
                          >
                            {c.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={c1Mutation.isPending}
                      className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs flex items-center justify-center gap-2 transition shadow-sm disabled:opacity-50"
                    >
                      {c1Mutation.isPending ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Recording Label...</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-4 h-4" />
                          <span>Submit Ground-Truth Confirmation</span>
                        </>
                      )}
                    </button>
                  </form>
                )}
              </div>
            )}
          </div>

          {/* C1 Summary Panel (1 col) */}
          <div className="space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <BarChart2 className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  C1 Evaluation Summary
                </h3>
              </div>

              {c1Summary ? (
                <div className="space-y-4 text-xs">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <span className="text-[11px] text-slate-400 block mb-0.5">Validated Items</span>
                      <span className="text-base font-bold text-slate-900">{c1Summary.n_items}</span>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <span className="text-[11px] text-slate-400 block mb-0.5">Agreement</span>
                      <span className="text-base font-bold text-emerald-600">{c1Summary.agreement_pct}%</span>
                    </div>
                  </div>

                  {/* Cohen's Kappa */}
                  <div className="p-3.5 rounded-xl bg-indigo-50/60 border border-indigo-100 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-indigo-900">Cohen's Kappa (Model vs Staff):</span>
                      <span className="font-bold text-indigo-700 text-sm">{c1Summary.cohen_kappa.toFixed(3)}</span>
                    </div>
                    <p className="text-[11px] text-indigo-800">
                      Band: <strong>{c1Summary.cohen_kappa_band}</strong>
                    </p>
                  </div>

                  {/* Macro-F1 */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <span className="text-slate-600 font-medium">Model Macro-F1:</span>
                    <span className="font-bold text-slate-900">{c1Summary.macro_f1.toFixed(3)}</span>
                  </div>

                  {/* Inter-rater agreement if available */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-0.5">
                    <span className="text-slate-500 font-medium block">Inter-Rater Agreement:</span>
                    {c1Summary.inter_rater_kappa !== null && c1Summary.inter_rater_kappa !== undefined ? (
                      <span className="font-bold text-indigo-600">
                        κ = {c1Summary.inter_rater_kappa.toFixed(3)} ({c1Summary.inter_rater_band})
                      </span>
                    ) : (
                      <span className="text-[11px] text-slate-400 italic">
                        Requires items validated by ≥ 2 reviewers.
                      </span>
                    )}
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-slate-400 text-xs">
                  Loading evaluation metrics...
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════
          TAB 2: C4 RECOMMENDATION APPROPRIATENESS RATING
          ═══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'c4' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Rating Pane (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            {isC4QueueLoading ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400">
                <Loader2 className="w-8 h-8 animate-spin mx-auto text-indigo-600 mb-2" />
                <span className="text-sm">Loading recommendation queue...</span>
              </div>
            ) : !activeC4Item ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
                <h3 className="text-base font-bold text-slate-900 mb-1">
                  All Recommendations Evaluated
                </h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  You have reviewed and rated all pending recommendations. Check aggregate NDCG and Precision@K metrics in the summary panel.
                </p>
              </div>
            ) : (
              <form onSubmit={handleC4Submit} className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-5">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100">
                        {activeC4Item.pid}
                      </span>
                      {activeC4Item.risk_tier && (
                        <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                          {activeC4Item.risk_tier} Risk
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Evaluating recommendation batch {activeC4Item.recommendation_id.slice(0, 8)}...
                    </p>
                  </div>

                  <span className="text-xs text-slate-400">
                    Week {activeC4Item.week_index + 1}
                  </span>
                </div>

                {/* Status messages */}
                {c4SuccessMsg && (
                  <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    <span>{c4SuccessMsg}</span>
                  </div>
                )}
                {c4Error && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                    <span>{c4Error}</span>
                  </div>
                )}

                {/* Candidate Recommendations List */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center justify-between">
                    <span>Ranked Candidates (C4 Output)</span>
                    <span className="text-[11px] text-slate-400 font-normal">Check all clinically suitable options</span>
                  </h4>

                  <div className="space-y-2.5">
                    {activeC4Item.candidates.map((c) => {
                      const isSuitable = suitableRanks.includes(c.rank);
                      return (
                        <div
                          key={c.rank}
                          className={`p-3.5 rounded-xl border transition ${
                            isSuitable
                              ? 'bg-indigo-50/40 border-indigo-300'
                              : 'bg-white border-slate-200'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-2.5">
                              <span className="w-6 h-6 rounded-lg bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center flex-shrink-0">
                                #{c.rank}
                              </span>
                              <div>
                                <span className="font-bold text-slate-900 text-xs block">
                                  {c.label}
                                </span>
                                <span className="text-[11px] text-slate-500">
                                  Student label: "{c.student_label}"
                                </span>
                                {c.rationale && (
                                  <p className="text-[11px] text-slate-600 mt-1 italic leading-relaxed">
                                    "{c.rationale}"
                                  </p>
                                )}
                              </div>
                            </div>

                            <label className="flex items-center gap-1.5 cursor-pointer text-xs font-semibold text-indigo-600 select-none">
                              <input
                                type="checkbox"
                                checked={isSuitable}
                                onChange={() => toggleRankSuitability(c.rank)}
                                className="rounded text-indigo-600 focus:ring-indigo-500"
                              />
                              <span>Suitable</span>
                            </label>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Rating Controls */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  {/* Appropriateness (1-5) */}
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <label className="block text-xs font-bold text-slate-700 mb-1.5">
                      Appropriateness Rating (1-5 Likert):
                    </label>
                    <div className="flex items-center gap-1.5">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setC4Appropriateness(star)}
                          className="p-1 focus:outline-none"
                        >
                          <Star
                            className={`w-6 h-6 ${
                              star <= c4Appropriateness
                                ? 'fill-amber-400 text-amber-400'
                                : 'fill-slate-200 text-slate-200'
                            }`}
                          />
                        </button>
                      ))}
                      <span className="ml-2 font-bold text-slate-800 text-xs">
                        {c4Appropriateness}/5
                      </span>
                    </div>
                  </div>

                  {/* Top-1 Acceptable Checkbox */}
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-center">
                    <label className="flex items-center gap-2 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={top1Acceptable}
                        onChange={(e) => setTop1Acceptable(e.target.checked)}
                        className="rounded text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-xs font-semibold text-slate-800">
                        Top-1 ranked choice is clinically acceptable
                      </span>
                    </label>
                    <p className="text-[11px] text-slate-500 mt-1 pl-6">
                      Verifies whether the primary suggested intervention should proceed directly.
                    </p>
                  </div>
                </div>

                {/* Qualitative Comment */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
                    <Lock className="w-3 h-3 text-indigo-500" />
                    <span>Qualitative evaluation feedback (Optional, private):</span>
                  </label>
                  <textarea
                    value={c4Comment}
                    onChange={(e) => setC4Comment(e.target.value.slice(0, 500))}
                    rows={2}
                    placeholder="Specific rationale on why the ranking order was appropriate or modified..."
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 resize-none"
                  />
                </div>

                {/* Submit Action */}
                <button
                  type="submit"
                  disabled={c4Mutation.isPending}
                  className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs flex items-center justify-center gap-2 transition shadow-sm disabled:opacity-50"
                >
                  {c4Mutation.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Saving Evaluation...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Submit Recommendation Evaluation</span>
                    </>
                  )}
                </button>
              </form>
            )}
          </div>

          {/* C4 Summary Panel (1 col) */}
          <div className="space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <BarChart2 className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  C4 Ranking Summary
                </h3>
              </div>

              {c4Summary ? (
                <div className="space-y-4 text-xs">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <span className="text-[11px] text-slate-400 block mb-0.5">Rated Batches</span>
                      <span className="text-base font-bold text-slate-900">{c4Summary.n}</span>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                      <span className="text-[11px] text-slate-400 block mb-0.5">Mean Rating</span>
                      <span className="text-base font-bold text-amber-600">{c4Summary.mean_appropriateness.toFixed(1)}/5</span>
                    </div>
                  </div>

                  {/* Precision & NDCG ranking metrics */}
                  <div className="p-3.5 rounded-xl bg-indigo-50/60 border border-indigo-100 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-indigo-900">Precision@1:</span>
                      <span className="font-bold text-indigo-700">{c4Summary.precision_at_1.toFixed(3)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-indigo-900">Precision@3:</span>
                      <span className="font-bold text-indigo-700">{c4Summary.precision_at_3.toFixed(3)}</span>
                    </div>
                    <div className="flex items-center justify-between pt-1 border-t border-indigo-200/50">
                      <span className="font-semibold text-indigo-900">NDCG@3:</span>
                      <span className="font-bold text-indigo-700">{c4Summary.ndcg_at_3.toFixed(3)}</span>
                    </div>
                  </div>

                  {/* Top-1 Acceptable Rate */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <span className="text-slate-600 font-medium">Top-1 Acceptable Rate:</span>
                    <span className="font-bold text-emerald-600">
                      {(c4Summary.top1_acceptable_rate * 100).toFixed(1)}%
                    </span>
                  </div>

                  {/* Review Mix */}
                  {c4Summary.acceptance_mix && (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1 text-[11px]">
                      <span className="font-semibold text-slate-700 block">Operational Review Mix:</span>
                      <div className="flex justify-between text-slate-600">
                        <span>Approved: {c4Summary.acceptance_mix.approved || 0}</span>
                        <span>Modified: {c4Summary.acceptance_mix.modified || 0}</span>
                        <span>Rejected: {c4Summary.acceptance_mix.rejected || 0}</span>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-6 text-center text-slate-400 text-xs">
                  Loading ranking metrics...
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
