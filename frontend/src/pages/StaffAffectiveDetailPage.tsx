import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  staffAffectiveApi,
  StaffAffectiveHistoryItem,
  StaffScrubbedMessageItem,
} from '../api/staffAffective';
import {
  ArrowLeft,
  ShieldCheck,
  Lock,
  Sparkles,
  AlertCircle,
  Calendar,
  MessageSquare,
  Activity,
  Info,
  Clock,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

const DISTRESS_CONFIG: Record<
  string,
  { label: string; color: string; stroke: string }
> = {
  exam_anxiety: { label: 'Exam Anxiety', color: 'text-amber-700', stroke: '#f59e0b' },
  conceptual_confusion: { label: 'Conceptual Confusion', color: 'text-purple-700', stroke: '#8b5cf6' },
  academic_helplessness: { label: 'Academic Helplessness', color: 'text-rose-700', stroke: '#ef4444' },
  course_frustration: { label: 'Course Frustration', color: 'text-orange-700', stroke: '#f97316' },
  motivation_erosion: { label: 'Motivation Erosion', color: 'text-indigo-700', stroke: '#6366f1' },
};

function getWeightShade(weight: number | null): string {
  if (weight === null) return '';
  if (weight >= 0.4) return 'bg-amber-300 text-amber-950 font-semibold px-1.5 py-0.5 rounded';
  if (weight >= 0.2) return 'bg-amber-200 text-amber-900 font-medium px-1 py-0.5 rounded';
  return 'bg-amber-100 text-amber-900 px-1 py-0.5 rounded';
}

export const StaffAffectiveDetailPage: React.FC = () => {
  const { pid } = useParams<{ pid: string }>();
  const [searchParams] = useSearchParams();
  const courseId = searchParams.get('course_id') || '';

  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);

  // 1. Fetch student's longitudinal history
  const {
    data: historyData,
    isLoading: isHistoryLoading,
    isError: isHistoryError,
    error: historyError,
  } = useQuery({
    queryKey: ['staffAffectiveHistory', pid, courseId],
    queryFn: () => staffAffectiveApi.getStudentHistory(pid!, courseId),
    enabled: !!pid && !!courseId,
  });

  const history = historyData?.history || [];

  // Initialize selected week to the latest available week
  useEffect(() => {
    if (history.length > 0 && selectedWeek === null) {
      setSelectedWeek(history[history.length - 1].week_index);
    }
  }, [history, selectedWeek]);

  // Selected week doc
  const currentWeekDoc: StaffAffectiveHistoryItem | undefined = history.find(
    (h) => h.week_index === selectedWeek
  );

  // 2. Fetch scrubbed messages for the selected week
  const {
    data: messages = [],
    isLoading: isMessagesLoading,
  } = useQuery<StaffScrubbedMessageItem[]>({
    queryKey: ['staffStudentMessages', pid, courseId, selectedWeek],
    queryFn: () => staffAffectiveApi.getStudentMessages(pid!, courseId, selectedWeek!),
    enabled: !!pid && !!courseId && selectedWeek !== null,
  });

  // Prepare chart data: array of { name: 'Week X', exam_anxiety: 0.4, ... }
  const chartData = history.map((item) => ({
    name: `Week ${item.week_index + 1}`,
    weekIndex: item.week_index,
    ...item.emotion_scores,
  }));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header Back Link */}
      <div className="mb-6">
        <Link
          to="/staff/affective"
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-indigo-600 transition mb-3"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to Student Support Cohort
        </Link>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight font-mono">
                {pid}
              </h1>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                <ShieldCheck className="w-3.5 h-3.5" />
                Active Consent Verified
              </span>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200">
                <Lock className="w-3 h-3" />
                Identity Protected (PID)
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Course: <span className="font-semibold text-slate-700">{courseId}</span> • Longitudinal Affective Distress Analysis (C1 XAI)
            </p>
          </div>
        </div>
      </div>

      {/* Loading state */}
      {isHistoryLoading && (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 shadow-sm text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-600 border-t-transparent mb-3" />
          <p className="text-sm text-slate-500">Loading student longitudinal history...</p>
        </div>
      )}

      {/* Error state */}
      {isHistoryError && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 p-6 rounded-2xl mb-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold">Unable to access student diagnostic view</h3>
              <p className="text-sm text-rose-700 mt-1">
                {(historyError as any)?.response?.data?.detail ||
                  'Access was denied or this student has not provided active research consent.'}
              </p>
              <Link
                to="/staff/affective"
                className="inline-block mt-3 text-xs font-semibold underline text-rose-900 hover:text-rose-950"
              >
                Return to student list
              </Link>
            </div>
          </div>
        </div>
      )}

      {!isHistoryLoading && !isHistoryError && history.length > 0 && (
        <div className="space-y-6">
          {/* Chart Section */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-600" />
                  Longitudinal Affective Trajectory
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Five-class emotional distress distribution tracked across observation weeks.
                </p>
              </div>
            </div>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={chartData}
                  margin={{ top: 10, right: 30, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} />
                  <YAxis
                    stroke="#64748b"
                    fontSize={12}
                    domain={[0, 1]}
                    tickLine={false}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip
                    formatter={(value: any, name: any) => [
                      `${(Number(value) * 100).toFixed(1)}%`,
                      DISTRESS_CONFIG[String(name)]?.label || name,
                    ]}
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      borderRadius: '0.75rem',
                      border: '1px solid #e2e8f0',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                      fontSize: '12px',
                    }}
                  />
                  <Legend
                    formatter={(value) => (
                      <span className="text-xs font-medium text-slate-700">
                        {DISTRESS_CONFIG[value]?.label || value}
                      </span>
                    )}
                  />
                  {Object.entries(DISTRESS_CONFIG).map(([key, cfg]) => (
                    <Line
                      key={key}
                      type="monotone"
                      dataKey={key}
                      name={key}
                      stroke={cfg.stroke}
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Week Selector Tabs */}
            <div className="mt-6 pt-4 border-t border-slate-100 flex items-center gap-2 overflow-x-auto pb-1">
              <span className="text-xs font-semibold text-slate-500 mr-2 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                Select Week:
              </span>
              {history.map((item) => (
                <button
                  key={item.week_index}
                  onClick={() => setSelectedWeek(item.week_index)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-xl transition ${
                    selectedWeek === item.week_index
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200/80'
                  }`}
                >
                  Week {item.week_index + 1}
                </button>
              ))}
            </div>
          </div>

          {/* Diagnostic Details for Selected Week */}
          {currentWeekDoc && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: Rationale & Scores */}
              <div className="lg:col-span-2 space-y-6">
                {/* Rationale Card */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                    <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-indigo-600" />
                      Diagnostic Rationale (Week {currentWeekDoc.week_index + 1})
                    </h3>
                    <span className="text-xs text-slate-400">Heuristic XAI Attribution</span>
                  </div>

                  <p className="text-sm text-slate-700 leading-relaxed bg-indigo-50/50 p-4 rounded-xl border border-indigo-100 font-sans">
                    {currentWeekDoc.rationale}
                  </p>

                  {/* Emotion Scores Breakdown Table */}
                  <div className="mt-5">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                      Emotion Scores Breakdown
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {Object.entries(DISTRESS_CONFIG).map(([key, cfg]) => {
                        const score = currentWeekDoc.emotion_scores[key] || 0.0;
                        const isDominant = currentWeekDoc.dominant_class === key;
                        return (
                          <div
                            key={key}
                            className={`p-2.5 rounded-xl border flex items-center justify-between ${
                              isDominant
                                ? 'bg-indigo-50 border-indigo-200 font-semibold'
                                : 'bg-slate-50 border-slate-100 text-slate-600'
                            }`}
                          >
                            <span className="flex items-center gap-1.5">
                              <span
                                className="w-2.5 h-2.5 rounded-full"
                                style={{ backgroundColor: cfg.stroke }}
                              />
                              {cfg.label}
                            </span>
                            <span className="font-mono">{(score * 100).toFixed(1)}%</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Scrubbed Messages Panel */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-indigo-600" />
                        Scrubbed Discussion & Journal Messages
                      </h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Extracted from canonical messages collection. Text is anonymised. Identity is hidden by design.
                      </p>
                    </div>
                    <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-600">
                      {messages.length} message{messages.length === 1 ? '' : 's'}
                    </span>
                  </div>

                  {isMessagesLoading && (
                    <div className="py-8 text-center text-slate-400 text-sm">
                      Loading messages...
                    </div>
                  )}

                  {!isMessagesLoading && messages.length === 0 && (
                    <div className="py-8 text-center text-slate-400 text-sm italic">
                      No scrubbed messages logged for this student in Week {selectedWeek! + 1}.
                    </div>
                  )}

                  {!isMessagesLoading && messages.length > 0 && (
                    <div className="space-y-3 mt-4">
                      {messages.map((msg) => (
                        <div
                          key={msg.message_id}
                          className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition"
                        >
                          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
                            <span className="uppercase font-semibold tracking-wider text-[10px] bg-slate-200/80 px-2 py-0.5 rounded text-slate-700">
                              {msg.source_type}
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {new Date(msg.timestamp).toLocaleString()}
                            </span>
                          </div>

                          <div className="text-sm text-slate-800 leading-relaxed font-sans">
                            {msg.segments.map((seg, sIdx) => {
                              if (seg.weight !== null) {
                                return (
                                  <span
                                    key={sIdx}
                                    className={getWeightShade(seg.weight)}
                                    title={`Linguistic attention driver (weight: ${seg.weight})`}
                                  >
                                    {seg.text}
                                  </span>
                                );
                              }
                              return <span key={sIdx}>{seg.text}</span>;
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Top Drivers & Meta */}
              <div className="space-y-6">
                {/* Status & Confidence Card */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">
                    Classification Status
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <div className="text-xs text-slate-400">Distress Level</div>
                      <div className="text-lg font-bold text-slate-900 capitalize mt-0.5">
                        {currentWeekDoc.stress_label}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400">Model Confidence</div>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-indigo-600 h-2 rounded-full"
                            style={{ width: `${currentWeekDoc.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-semibold font-mono text-slate-700">
                          {(currentWeekDoc.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400">Total Observations</div>
                      <div className="text-sm font-semibold text-slate-700 mt-0.5">
                        {currentWeekDoc.message_count} text items analysed
                      </div>
                    </div>
                  </div>
                </div>

                {/* Top Drivers Card */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      Language Attention Drivers
                    </h3>
                    <Info className="w-3.5 h-3.5 text-slate-400" />
                  </div>
                  <p className="text-xs text-slate-500 mb-3">
                    Tokens driving the distress classification, shaded and weighted by model attribution.
                  </p>

                  {currentWeekDoc.top_drivers.length === 0 ? (
                    <p className="text-xs text-slate-400 italic">
                      No linguistic driver tokens reported for this week.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {currentWeekDoc.top_drivers.map((d, dIdx) => (
                        <div
                          key={dIdx}
                          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs border border-amber-200/80 ${
                            d.weight >= 0.4
                              ? 'bg-amber-300 text-amber-950 font-semibold'
                              : d.weight >= 0.2
                              ? 'bg-amber-200 text-amber-900 font-medium'
                              : 'bg-amber-100 text-amber-900'
                          }`}
                        >
                          <span>"{d.token_or_marker}"</span>
                          <span className="text-[10px] font-mono opacity-80">
                            {d.weight.toFixed(2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-400 flex items-center gap-2">
                    <span className="w-3 h-3 rounded bg-amber-100 border border-amber-200" />
                    <span>Low &lt;0.2</span>
                    <span className="w-3 h-3 rounded bg-amber-200 border border-amber-300 ml-1" />
                    <span>Mid 0.2-0.4</span>
                    <span className="w-3 h-3 rounded bg-amber-300 border border-amber-400 ml-1" />
                    <span>High &ge;0.4</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
