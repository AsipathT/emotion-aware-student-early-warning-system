import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  X,
  Brain,
  Activity,
  GraduationCap,
  TrendingDown,
  TrendingUp,
  Minus,
  Zap,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
  ShieldCheck,
  Send,
  Loader2,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { analyticsApi, StudentRiskDetail } from '../../api/analytics';

interface StudentRiskModalProps {
  pid: string | null;
  courseId: string;
  onClose: () => void;
}

export const StudentRiskModal: React.FC<StudentRiskModalProps> = ({
  pid,
  courseId,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'risk_trajectory' | 'behavioral_telemetry'>('risk_trajectory');
  const [actionRecorded, setActionRecorded] = useState<Record<string, boolean>>({});

  const {
    data: detail,
    isLoading,
    isError,
  } = useQuery<StudentRiskDetail>({
    queryKey: ['student-risk-detail', pid, courseId],
    queryFn: () => analyticsApi.getStudentRiskDetail(pid!, courseId),
    enabled: !!pid,
  });

  if (!pid) return null;

  const handleAction = (title: string) => {
    setActionRecorded((prev) => ({ ...prev, [title]: true }));
  };

  const getTierBadge = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'medium':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      default:
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    }
  };

  const getTrajectoryIcon = (label: string) => {
    switch (label.toLowerCase()) {
      case 'declining':
        return <TrendingDown className="w-4 h-4 text-red-600 inline mr-1" />;
      case 'improving':
        return <TrendingUp className="w-4 h-4 text-emerald-600 inline mr-1" />;
      case 'volatile':
        return <Zap className="w-4 h-4 text-amber-600 inline mr-1" />;
      default:
        return <Minus className="w-4 h-4 text-blue-600 inline mr-1" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-5 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-600/30 border border-indigo-400/40 flex items-center justify-center text-indigo-300 font-bold text-lg">
              {detail?.student.name.charAt(0) || 'S'}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-xl font-bold tracking-tight text-white">
                  {detail?.student.name || 'Loading Student...'}
                </h2>
                {detail && (
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase tracking-wider border ${getTierBadge(
                      detail.latest_assessment.risk_tier
                    )}`}
                  >
                    {detail.latest_assessment.risk_tier} Risk
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-300 mt-0.5 flex items-center space-x-3">
                <span>
                  ID: <span className="font-mono text-indigo-200">{detail?.student.student_id}</span>
                </span>
                <span>&bull;</span>
                <span className="flex items-center">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 mr-1" />
                  PID: <span className="font-mono text-slate-300 ml-1">{detail?.student.pid}</span>
                </span>
                <span>&bull;</span>
                <span>{detail?.student.course_title}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800/80 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-3">
              <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
              <p className="text-sm text-slate-500 font-medium">
                Synthesizing student longitudinal multimodal telemetry...
              </p>
            </div>
          ) : isError || !detail ? (
            <div className="p-8 text-center bg-red-50 rounded-xl border border-red-200">
              <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-2" />
              <p className="text-base font-semibold text-red-800">
                Failed to load student risk assessment details
              </p>
              <p className="text-xs text-red-600 mt-1">
                Please verify database records exist for student PID: {pid}
              </p>
            </div>
          ) : (
            <>
              {/* Snapshot KPI Grid */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Risk Score */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                    Composite Risk Score
                  </span>
                  <div className="mt-2 flex items-baseline space-x-2">
                    <span className="text-3xl font-extrabold text-slate-900">
                      {(detail.latest_assessment.risk_score * 100).toFixed(1)}%
                    </span>
                    <span className="text-xs text-slate-500">
                      (Week {detail.latest_assessment.week_index + 1})
                    </span>
                  </div>
                  <div className="w-full bg-slate-200 h-2 rounded-full mt-3 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        detail.latest_assessment.risk_score >= 0.7
                          ? 'bg-red-500'
                          : detail.latest_assessment.risk_score >= 0.4
                          ? 'bg-amber-500'
                          : 'bg-emerald-500'
                      }`}
                      style={{ width: `${detail.latest_assessment.risk_score * 100}%` }}
                    />
                  </div>
                </div>

                {/* Trajectory */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                    Engagement Trajectory
                  </span>
                  <div className="mt-2 flex items-center space-x-2">
                    <span className="text-xl font-bold capitalize text-slate-900 flex items-center">
                      {getTrajectoryIcon(detail.latest_assessment.trajectory_label)}
                      {detail.latest_assessment.trajectory_label}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    Model Confidence: <span className="font-semibold text-slate-700">{(detail.latest_assessment.trajectory_confidence * 100).toFixed(0)}%</span>
                  </p>
                </div>

                {/* Modality Attribution */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 col-span-1 md:col-span-2">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                    Multimodal Attribution Breakdown (C1, C2, C3)
                  </span>
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center text-xs justify-between">
                      <span className="flex items-center text-slate-700 font-medium">
                        <Brain className="w-3.5 h-3.5 text-purple-600 mr-1.5" />
                        Affective Distress (C1)
                      </span>
                      <span className="font-bold text-slate-900">
                        {(detail.latest_assessment.modality_contributions.affective * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex items-center text-xs justify-between">
                      <span className="flex items-center text-slate-700 font-medium">
                        <Activity className="w-3.5 h-3.5 text-blue-600 mr-1.5" />
                        Behavioral Engagement (C2)
                      </span>
                      <span className="font-bold text-slate-900">
                        {(detail.latest_assessment.modality_contributions.behavioral * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex items-center text-xs justify-between">
                      <span className="flex items-center text-slate-700 font-medium">
                        <GraduationCap className="w-3.5 h-3.5 text-emerald-600 mr-1.5" />
                        Academic Retention (C3)
                      </span>
                      <span className="font-bold text-slate-900">
                        {(detail.latest_assessment.modality_contributions.academic * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Key Drivers Tags */}
              {detail.latest_assessment.top_drivers.length > 0 && (
                <div className="bg-amber-50/70 border border-amber-200 p-3.5 rounded-xl flex items-start space-x-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wider">
                      Primary Early Warning Indicators Detected:
                    </h4>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {detail.latest_assessment.top_drivers.map((driver, idx) => (
                        <span
                          key={idx}
                          className="px-2.5 py-0.5 bg-amber-100 text-amber-800 text-xs font-semibold rounded-md border border-amber-200"
                        >
                          {driver.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Longitudinal Charts Section (Feature 29) */}
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
                  <div>
                    <h3 className="text-base font-bold text-slate-900">
                      Longitudinal Trajectory Visualization (Feature 29)
                    </h3>
                    <p className="text-xs text-slate-500">
                      Observation progression across academic term weeks
                    </p>
                  </div>
                  <div className="flex space-x-1 bg-slate-100 p-1 rounded-lg">
                    <button
                      onClick={() => setActiveTab('risk_trajectory')}
                      className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                        activeTab === 'risk_trajectory'
                          ? 'bg-white text-indigo-700 shadow-xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Risk & Modalities
                    </button>
                    <button
                      onClick={() => setActiveTab('behavioral_telemetry')}
                      className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                        activeTab === 'behavioral_telemetry'
                          ? 'bg-white text-indigo-700 shadow-xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Behavioral Telemetry
                    </button>
                  </div>
                </div>

                <div className="h-72 w-full pt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    {activeTab === 'risk_trajectory' ? (
                      <LineChart data={detail.longitudinal_trends}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="week_label" stroke="#64748b" textAnchor="middle" />
                        <YAxis stroke="#64748b" domain={[0, 100]} unit="%" />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#0f172a',
                            borderColor: '#334155',
                            color: '#fff',
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px' }} />
                        <Line
                          type="monotone"
                          dataKey={(d) => Math.round(d.risk_score * 100)}
                          name="Overall Risk Score (%)"
                          stroke="#ef4444"
                          strokeWidth={3}
                          dot={{ r: 5 }}
                          activeDot={{ r: 8 }}
                        />
                        <Line
                          type="monotone"
                          dataKey="affective_pct"
                          name="Affective Contrib (%)"
                          stroke="#a855f7"
                          strokeWidth={2}
                          strokeDasharray="4 4"
                        />
                        <Line
                          type="monotone"
                          dataKey="behavioral_pct"
                          name="Behavioral Contrib (%)"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          strokeDasharray="4 4"
                        />
                        <Line
                          type="monotone"
                          dataKey="academic_pct"
                          name="Academic Contrib (%)"
                          stroke="#10b981"
                          strokeWidth={2}
                          strokeDasharray="4 4"
                        />
                      </LineChart>
                    ) : (
                      <BarChart data={detail.longitudinal_trends}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="week_label" stroke="#64748b" />
                        <YAxis stroke="#64748b" />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#0f172a',
                            borderColor: '#334155',
                            color: '#fff',
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px' }} />
                        <Bar dataKey="login_count" name="Logins" fill="#6366f1" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="video_completion_pct" name="Video Avg (%)" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="attendance_pct" name="Attendance (%)" fill="#10b981" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    )}
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Recommended Cause-Matched Interventions (Feature 28) */}
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-5 h-5 text-indigo-600" />
                  <h3 className="text-base font-bold text-slate-900">
                    Cause-Matched Recommended Interventions
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {detail.recommended_interventions.map((rec, idx) => {
                    const isDone = actionRecorded[rec.title];
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border transition-all ${
                          isDone
                            ? 'bg-emerald-50/60 border-emerald-300'
                            : 'bg-slate-50/80 border-slate-200 hover:border-indigo-300'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-800">
                            {rec.category}
                          </span>
                          <span className="text-xs font-medium text-amber-700 flex items-center">
                            <Clock className="w-3 h-3 mr-1" />
                            {rec.urgency}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-slate-900 mt-2">
                          {rec.title}
                        </h4>
                        <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                          {rec.description}
                        </p>
                        <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between">
                          <span className="text-xs text-slate-400">
                            Action: <span className="font-mono text-slate-600">{rec.action_type}</span>
                          </span>
                          <button
                            onClick={() => handleAction(rec.title)}
                            disabled={isDone}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                              isDone
                                ? 'bg-emerald-600 text-white cursor-default'
                                : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs'
                            }`}
                          >
                            {isDone ? (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>Recorded</span>
                              </>
                            ) : (
                              <>
                                <Send className="w-3.5 h-3.5" />
                                <span>Initiate Action</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <p className="text-xs text-slate-500">
            Feature 28 & 29 &bull; Multimodal Longitudinal Diagnostic View
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white hover:bg-slate-100 text-slate-700 text-sm font-semibold rounded-xl border border-slate-300 transition-colors"
          >
            Close Detail
          </button>
        </div>
      </div>
    </div>
  );
};
export default StudentRiskModal;
