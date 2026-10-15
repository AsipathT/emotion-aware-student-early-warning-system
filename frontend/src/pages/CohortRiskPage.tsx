import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ShieldAlert,
  Users,
  Brain,
  TrendingDown,
  TrendingUp,
  Minus,
  Zap,
  Search,
  Filter,
  Sparkles,
  ChevronRight,
  ShieldCheck,
  AlertTriangle,
  RotateCcw,
  Loader2,
  BookOpen,
  Calendar,
  Layers,
} from 'lucide-react';
import { analyticsApi, CohortRiskResponse, StudentRiskRow } from '../api/analytics';
import { StudentRiskModal } from '../components/analytics/StudentRiskModal';
import { SyntheticDataModal } from '../components/analytics/SyntheticDataModal';

export const CohortRiskPage: React.FC = () => {
  const [selectedCourseId, setSelectedCourseId] = useState<string>('CS101');
  const [selectedWeek, setSelectedWeek] = useState<number | undefined>(undefined);
  const [riskTierFilter, setRiskTierFilter] = useState<string>('all');
  const [trajectoryFilter, setTrajectoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modals state
  const [inspectPid, setInspectPid] = useState<string | null>(null);
  const [isSyntheticModalOpen, setIsSyntheticModalOpen] = useState<boolean>(false);

  // Query cohort risk data
  const {
    data: cohortData,
    isLoading,
    isFetching,
    refetch,
  } = useQuery<CohortRiskResponse>({
    queryKey: [
      'cohort-risk',
      selectedCourseId,
      selectedWeek,
      riskTierFilter,
      trajectoryFilter,
      searchQuery,
    ],
    queryFn: () =>
      analyticsApi.getCohortRisk({
        course_id: selectedCourseId,
        week_index: selectedWeek,
        risk_tier: riskTierFilter,
        trajectory: trajectoryFilter,
        search: searchQuery,
      }),
  });

  const getTierBadge = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      default:
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    }
  };

  const getTrajectoryIcon = (label: string) => {
    switch (label.toLowerCase()) {
      case 'declining':
        return <TrendingDown className="w-3.5 h-3.5 text-red-600 inline mr-1" />;
      case 'improving':
        return <TrendingUp className="w-3.5 h-3.5 text-emerald-600 inline mr-1" />;
      case 'volatile':
        return <Zap className="w-3.5 h-3.5 text-amber-600 inline mr-1" />;
      default:
        return <Minus className="w-3.5 h-3.5 text-blue-600 inline mr-1" />;
    }
  };

  const summary = cohortData?.summary;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-xl border border-slate-800 relative overflow-hidden">
        <div className="absolute right-0 top-0 translate-x-10 -translate-y-10 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 bg-indigo-500/20 text-indigo-300 rounded-full text-xs font-bold tracking-wider uppercase border border-indigo-500/30">
                Feature 27 &bull; Early Warning Intelligence
              </span>
              {isFetching && (
                <span className="flex items-center text-xs text-indigo-300 space-x-1">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Syncing...</span>
                </span>
              )}
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight mt-2 text-white">
              Cohort Risk Overview Dashboard
            </h1>
            <p className="mt-1 text-slate-300 text-sm max-w-2xl">
              Multimodal student attrition detection, longitudinal engagement trajectories,
              and cause-matched early intervention alerts.
            </p>
          </div>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setIsSyntheticModalOpen(true)}
              className="px-4 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white rounded-xl text-xs font-bold shadow-md hover:shadow-indigo-500/25 flex items-center space-x-2 transition-all"
            >
              <Sparkles className="w-4 h-4 text-indigo-200" />
              <span>Synthetic Data Generator (F41)</span>
            </button>
            <button
              onClick={() => refetch()}
              className="px-3.5 py-2.5 bg-white/10 hover:bg-white/20 text-white rounded-xl text-xs font-semibold backdrop-blur-xs border border-white/10 flex items-center space-x-1.5 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-300" />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Course & Week Controls Bar */}
        <div className="mt-6 pt-5 border-t border-slate-800 flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <BookOpen className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-semibold text-slate-300">Course:</span>
            <select
              value={selectedCourseId}
              onChange={(e) => {
                setSelectedCourseId(e.target.value);
                setSelectedWeek(undefined);
              }}
              className="bg-slate-800/90 text-white text-xs font-semibold rounded-lg px-3 py-1.5 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {cohortData?.available_courses?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.course_code ? `${c.course_code} - ` : ''}{c.title}
                </option>
              ))}
              <option value="CS101">CS101 - Introduction to Computer Systems</option>
              <option value="SE4020">SE4020 - Advanced Software Engineering</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <Calendar className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-semibold text-slate-300">Observation Week:</span>
            <select
              value={selectedWeek !== undefined ? selectedWeek : cohortData?.current_week ?? 0}
              onChange={(e) => setSelectedWeek(Number(e.target.value))}
              className="bg-slate-800/90 text-white text-xs font-semibold rounded-lg px-3 py-1.5 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {cohortData?.available_weeks?.length ? (
                cohortData.available_weeks.map((w) => (
                  <option key={w} value={w}>
                    Week {w + 1}
                  </option>
                ))
              ) : (
                <option value={0}>Week 1</option>
              )}
            </select>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Card 1: Total Students */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center space-x-4">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Cohort Monitored
            </p>
            <p className="text-2xl font-black text-slate-900">
              {summary?.total_students ?? 0}
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">Enrolled active students</p>
          </div>
        </div>

        {/* Card 2: High/Critical Risk Alarm */}
        <div className="bg-white p-5 rounded-2xl border border-red-100 shadow-xs flex items-center space-x-4 relative overflow-hidden">
          <div className="p-3 bg-red-50 text-red-600 rounded-xl">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Urgent Risk Attrition
              </p>
              {(summary?.high_risk_percentage ?? 0) > 20 && (
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                </span>
              )}
            </div>
            <p className="text-2xl font-black text-red-600">
              {summary?.high_risk_percentage ?? 0}%
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              {(summary?.tier_distribution.critical ?? 0) + (summary?.tier_distribution.high ?? 0)} high/critical students
            </p>
          </div>
        </div>

        {/* Card 3: Avg Risk Score */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center space-x-4">
          <div className="p-3 bg-amber-50 text-amber-600 rounded-xl">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Mean Risk Index
            </p>
            <p className="text-2xl font-black text-slate-900">
              {((summary?.avg_risk_score ?? 0) * 100).toFixed(1)}%
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">Multimodal composite score</p>
          </div>
        </div>

        {/* Card 4: Dominant Modality */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Modality Attribution
          </p>
          <div className="mt-2.5 space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-purple-700 font-medium flex items-center">
                <Brain className="w-3 h-3 mr-1" /> Affective:
              </span>
              <span className="font-bold text-slate-800">
                {((summary?.avg_modality_contributions.affective ?? 0.33) * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-blue-700 font-medium flex items-center">
                <Layers className="w-3 h-3 mr-1" /> Behavioral:
              </span>
              <span className="font-bold text-slate-800">
                {((summary?.avg_modality_contributions.behavioral ?? 0.34) * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-emerald-700 font-medium flex items-center">
                <BookOpen className="w-3 h-3 mr-1" /> Academic:
              </span>
              <span className="font-bold text-slate-800">
                {((summary?.avg_modality_contributions.academic ?? 0.33) * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Trajectory Breakdown & Distribution Bar (Feature 29) */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-3.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-700 uppercase tracking-wider">
            <span>Engagement Trajectory Distribution (Feature 29)</span>
          </div>
          <span className="text-xs text-slate-400">Click a cohort segment to filter students</span>
        </div>

        {/* Visual Multi-Segment Trajectory Bar */}
        {(() => {
          const dec = summary?.trajectory_distribution.declining ?? 0;
          const vol = summary?.trajectory_distribution.volatile ?? 0;
          const sta = summary?.trajectory_distribution.stable ?? 0;
          const imp = summary?.trajectory_distribution.improving ?? 0;
          const total = dec + vol + sta + imp || 1;

          return (
            <div className="space-y-3">
              <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
                {dec > 0 && (
                  <div
                    style={{ width: `${(dec / total) * 100}%` }}
                    className="bg-red-500 hover:bg-red-600 transition-all cursor-pointer"
                    title={`Declining: ${dec} (${Math.round((dec / total) * 100)}%)`}
                    onClick={() => setTrajectoryFilter('declining')}
                  />
                )}
                {vol > 0 && (
                  <div
                    style={{ width: `${(vol / total) * 100}%` }}
                    className="bg-amber-500 hover:bg-amber-600 transition-all cursor-pointer"
                    title={`Volatile: ${vol} (${Math.round((vol / total) * 100)}%)`}
                    onClick={() => setTrajectoryFilter('volatile')}
                  />
                )}
                {sta > 0 && (
                  <div
                    style={{ width: `${(sta / total) * 100}%` }}
                    className="bg-blue-500 hover:bg-blue-600 transition-all cursor-pointer"
                    title={`Stable: ${sta} (${Math.round((sta / total) * 100)}%)`}
                    onClick={() => setTrajectoryFilter('stable')}
                  />
                )}
                {imp > 0 && (
                  <div
                    style={{ width: `${(imp / total) * 100}%` }}
                    className="bg-emerald-500 hover:bg-emerald-600 transition-all cursor-pointer"
                    title={`Improving: ${imp} (${Math.round((imp / total) * 100)}%)`}
                    onClick={() => setTrajectoryFilter('improving')}
                  />
                )}
              </div>

              {/* Trajectory Pills */}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => setTrajectoryFilter(trajectoryFilter === 'declining' ? 'all' : 'declining')}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                    trajectoryFilter === 'declining'
                      ? 'bg-red-600 text-white border-red-700 shadow-sm'
                      : 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100'
                  }`}
                >
                  <TrendingDown className="w-3.5 h-3.5" />
                  <span>Declining:</span>
                  <span className="font-black">{dec}</span>
                  <span className="text-[10px] opacity-80">({Math.round((dec / total) * 100)}%)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setTrajectoryFilter(trajectoryFilter === 'volatile' ? 'all' : 'volatile')}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                    trajectoryFilter === 'volatile'
                      ? 'bg-amber-600 text-white border-amber-700 shadow-sm'
                      : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
                  }`}
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>Volatile:</span>
                  <span className="font-black">{vol}</span>
                  <span className="text-[10px] opacity-80">({Math.round((vol / total) * 100)}%)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setTrajectoryFilter(trajectoryFilter === 'stable' ? 'all' : 'stable')}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                    trajectoryFilter === 'stable'
                      ? 'bg-blue-600 text-white border-blue-700 shadow-sm'
                      : 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
                  }`}
                >
                  <Minus className="w-3.5 h-3.5" />
                  <span>Stable:</span>
                  <span className="font-black">{sta}</span>
                  <span className="text-[10px] opacity-80">({Math.round((sta / total) * 100)}%)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setTrajectoryFilter(trajectoryFilter === 'improving' ? 'all' : 'improving')}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                    trajectoryFilter === 'improving'
                      ? 'bg-emerald-600 text-white border-emerald-700 shadow-sm'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                  }`}
                >
                  <TrendingUp className="w-3.5 h-3.5" />
                  <span>Improving:</span>
                  <span className="font-black">{imp}</span>
                  <span className="text-[10px] opacity-80">({Math.round((imp / total) * 100)}%)</span>
                </button>

                {trajectoryFilter !== 'all' && (
                  <button
                    type="button"
                    onClick={() => setTrajectoryFilter('all')}
                    className="text-xs text-slate-500 hover:text-slate-700 underline font-medium ml-2"
                  >
                    Clear Filter
                  </button>
                )}
              </div>
            </div>
          );
        })()}
      </div>

      {/* Roster Controls: Search & Filters */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by student name, ID, PID, or risk driver tag..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
            />
          </div>

          {/* Tier Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold text-slate-500 mr-1 flex items-center">
              <Filter className="w-3 h-3 mr-1" /> Tier:
            </span>
            {['all', 'critical', 'high', 'medium', 'low'].map((tier) => (
              <button
                key={tier}
                onClick={() => setRiskTierFilter(tier)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                  riskTierFilter === tier
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                {tier}
              </button>
            ))}
          </div>

          {/* Trajectory Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold text-slate-500 mr-1">Trend:</span>
            {['all', 'declining', 'volatile', 'stable', 'improving'].map((traj) => (
              <button
                key={traj}
                onClick={() => setTrajectoryFilter(traj)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold capitalize transition-all ${
                  trajectoryFilter === traj
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                {traj}
              </button>
            ))}
          </div>
        </div>

        {/* Roster Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Student</th>
                <th className="py-3 px-4">Privacy PID (F5)</th>
                <th className="py-3 px-4">Risk Probability</th>
                <th className="py-3 px-4">Risk Tier</th>
                <th className="py-3 px-4">Trajectory (F29)</th>
                <th className="py-3 px-4">Primary Driver</th>
                <th className="py-3 px-4">Top Warning Indicators</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto mb-2" />
                    <span>Loading cohort risk assessments...</span>
                  </td>
                </tr>
              ) : !cohortData?.students || cohortData.students.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center">
                    <div className="max-w-md mx-auto space-y-3">
                      <ShieldAlert className="w-10 h-10 text-slate-400 mx-auto" />
                      <p className="text-sm font-bold text-slate-700">
                        No risk assessment records found for this selection
                      </p>
                      <p className="text-xs text-slate-500">
                        No telemetry has been ingested for this week or filter combination yet.
                        Use the Synthetic Data Generator to populate test cohorts.
                      </p>
                      <button
                        onClick={() => setIsSyntheticModalOpen(true)}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl text-xs transition-colors shadow-sm inline-flex items-center space-x-1.5"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Generate Synthetic Cohort</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                cohortData.students.map((student: StudentRiskRow) => (
                  <tr
                    key={student.pid}
                    className="hover:bg-slate-50/70 transition-colors group"
                  >
                    {/* Student Name & ID */}
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center text-xs flex-shrink-0">
                          {student.name.charAt(0)}
                        </div>
                        <div>
                          <p className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                            {student.name}
                          </p>
                          <p className="text-[11px] font-mono text-slate-500">
                            {student.student_id}
                          </p>
                        </div>
                      </div>
                    </td>

                    {/* Pseudonym PID */}
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-mono text-[11px] border border-slate-200">
                        <ShieldCheck className="w-3 h-3 text-emerald-600 mr-1" />
                        {student.pid}
                      </span>
                    </td>

                    {/* Risk Score */}
                    <td className="py-3 px-4">
                      <div className="w-28 space-y-1">
                        <div className="flex justify-between items-center text-[11px]">
                          <span className="font-bold text-slate-900">
                            {(student.risk_score * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              student.risk_score >= 0.7
                                ? 'bg-red-500'
                                : student.risk_score >= 0.4
                                ? 'bg-amber-500'
                                : 'bg-emerald-500'
                            }`}
                            style={{ width: `${student.risk_score * 100}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Risk Tier */}
                    <td className="py-3 px-4">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider border ${getTierBadge(
                          student.risk_tier
                        )}`}
                      >
                        {student.risk_tier}
                      </span>
                    </td>

                    {/* Trajectory */}
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center text-xs capitalize font-semibold text-slate-700">
                        {getTrajectoryIcon(student.trajectory_label)}
                        {student.trajectory_label}
                      </span>
                      <span className="text-[10px] text-slate-400 block ml-4">
                        {(student.trajectory_confidence * 100).toFixed(0)}% conf
                      </span>
                    </td>

                    {/* Primary Driver */}
                    <td className="py-3 px-4">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                          student.primary_driver_modality === 'Affective'
                            ? 'bg-purple-50 text-purple-700 border border-purple-200'
                            : student.primary_driver_modality === 'Behavioral'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        {student.primary_driver_modality}
                      </span>
                    </td>

                    {/* Top Warning Indicators */}
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {student.top_drivers.slice(0, 2).map((driver, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-[10px] font-medium border border-slate-200"
                          >
                            {driver.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setInspectPid(student.pid)}
                        className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold rounded-lg text-xs inline-flex items-center space-x-1 border border-indigo-200 transition-all hover:scale-102"
                      >
                        <span>Inspect Profile</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Student Risk Modal (Features 28 & 29) */}
      {inspectPid && (
        <StudentRiskModal
          pid={inspectPid}
          courseId={selectedCourseId}
          onClose={() => setInspectPid(null)}
        />
      )}

      {/* Synthetic Data Generator Modal (Feature 41) */}
      <SyntheticDataModal
        isOpen={isSyntheticModalOpen}
        onClose={() => setIsSyntheticModalOpen(false)}
        availableCourses={cohortData?.available_courses || []}
        currentCourseId={selectedCourseId}
      />
    </div>
  );
};
export default CohortRiskPage;
