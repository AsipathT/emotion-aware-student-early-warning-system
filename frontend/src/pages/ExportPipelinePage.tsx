import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  exportPipelineApi,
  Envelope,
  TextMessageRecord,
  BehaviorWeeklyRecord,
  AcademicRecord,
  PipelineStatusResponse,
} from '../api/exportPipeline';
import { coursesApi, CourseResponse } from '../api/courses';
import {
  Download,
  Database,
  Cpu,
  RefreshCw,
  FileSpreadsheet,
  FileCode,
  Filter,
  CheckCircle2,
  AlertCircle,
  Play,
  Clock,
  MessageSquare,
  Activity,
  GraduationCap,
} from 'lucide-react';

type DatasetType = 'behavior' | 'academic' | 'messages';

export const ExportPipelinePage: React.FC = () => {
  const queryClient = useQueryClient();

  // Active Top Tab
  const [activeTab, setActiveTab] = useState<'export' | 'pipeline'>('export');

  // Export State
  const [selectedDataset, setSelectedDataset] = useState<DatasetType>('behavior');
  const [selectedCourse, setSelectedCourse] = useState<string>('');
  const [weekFrom, setWeekFrom] = useState<number | ''>('');
  const [weekTo, setWeekTo] = useState<number | ''>('');
  const [pidFilter, setPidFilter] = useState<string>('');
  const [pageSize, setPageSize] = useState<number>(50);

  // Pipeline Trigger State
  const [pipelineCourse, setPipelineCourse] = useState<string>('');
  const [pipelineWeek, setPipelineWeek] = useState<number>(1);
  const [pipelineFeedback, setPipelineFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  // 1. Fetch courses list for dropdowns
  const { data: courses = [] } = useQuery<CourseResponse[]>({
    queryKey: ['allCourses'],
    queryFn: coursesApi.getCourses,
  });

  // 2. Query Export Data
  const exportParams = {
    course_id: selectedCourse || undefined,
    week_from: weekFrom !== '' ? Number(weekFrom) : undefined,
    week_to: weekTo !== '' ? Number(weekTo) : undefined,
    pid: pidFilter.trim() || undefined,
    page: 1,
    page_size: pageSize,
  };

  const {
    data: exportData,
    isLoading: isLoadingExport,
    isRefetching: isRefetchingExport,
    refetch: refetchExport,
  } = useQuery<Envelope<any[]>>({
    queryKey: ['exportData', selectedDataset, exportParams],
    queryFn: async () => {
      if (selectedDataset === 'behavior') {
        return (await exportPipelineApi.getBehavior(exportParams)) as Envelope<any[]>;
      } else if (selectedDataset === 'academic') {
        return (await exportPipelineApi.getAcademic(exportParams)) as Envelope<any[]>;
      } else {
        return (await exportPipelineApi.getMessages(exportParams)) as Envelope<any[]>;
      }
    },
  });

  // 3. Query Pipeline Status
  const {
    data: pipelineStatus,
    isRefetching: isRefetchingPipeline,
    refetch: refetchPipeline,
  } = useQuery<PipelineStatusResponse>({
    queryKey: ['pipelineStatus'],
    queryFn: exportPipelineApi.getPipelineStatus,
    refetchInterval: 15000, // Poll every 15s
  });

  // 4. Trigger Pipeline Mutation
  const triggerMutation = useMutation({
    mutationFn: () =>
      exportPipelineApi.triggerWeeklyPipeline({
        course_id: pipelineCourse || undefined,
        week_index: pipelineWeek,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['pipelineStatus'] });
      queryClient.invalidateQueries({ queryKey: ['exportData'] });
      const recordsCreated = data?.data?.behavior_records_created ?? 0;
      setPipelineFeedback({
        type: 'success',
        message: `Pipeline ran successfully! Generated ${recordsCreated} weekly behavioral records for week ${pipelineWeek}.`,
      });
      setTimeout(() => setPipelineFeedback(null), 6000);
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || 'Pipeline execution failed.';
      setPipelineFeedback({
        type: 'error',
        message: msg,
      });
    },
  });

  // Export File Converters
  const handleDownloadJSON = () => {
    if (!exportData) return;
    const jsonStr = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `export_${selectedDataset}_${selectedCourse || 'all'}_w${weekFrom || 0}-${weekTo || 'all'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadCSV = () => {
    if (!exportData || !Array.isArray(exportData.data) || exportData.data.length === 0) return;
    const items = exportData.data;
    const headers = Object.keys(items[0]);
    const csvRows: string[] = [];

    // Header row
    csvRows.push(headers.join(','));

    // Data rows
    for (const row of items) {
      const values = headers.map((header) => {
        const val = row[header];
        if (val === null || val === undefined) return '';
        const escaped = ('' + val).replace(/"/g, '""');
        return `"${escaped}"`;
      });
      csvRows.push(values.join(','));
    }

    const csvStr = csvRows.join('\n');
    const blob = new Blob([csvStr], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `export_${selectedDataset}_${selectedCourse || 'all'}_w${weekFrom || 0}-${weekTo || 'all'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 px-3 py-1 bg-indigo-50 text-indigo-700 rounded-xl text-xs font-bold mb-2">
            <Database className="w-3.5 h-3.5" />
            <span>Research & Learning Analytics Hub</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Data Export & Telemetry Pipeline
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">
            Export de-identified multi-modal datasets for ML experiments (Feature 42) and trigger weekly clickstream aggregation pipelines (Feature 20).
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="inline-flex p-1 bg-slate-200/80 rounded-2xl border border-slate-200 self-start md:self-auto">
          <button
            onClick={() => setActiveTab('export')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition ${
              activeTab === 'export'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Download className="w-4 h-4" />
            <span>Research Export (F42)</span>
          </button>
          <button
            onClick={() => setActiveTab('pipeline')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition ${
              activeTab === 'pipeline'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Cpu className="w-4 h-4" />
            <span>Weekly Pipeline (F20)</span>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: DATA EXPORT FOR EXPERIMENTS (FEATURE 42)                          */}
      {/* ========================================================================= */}
      {activeTab === 'export' && (
        <div className="space-y-6">
          {/* Dataset Type Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              onClick={() => setSelectedDataset('behavior')}
              className={`p-5 rounded-2xl border text-left transition relative overflow-hidden ${
                selectedDataset === 'behavior'
                  ? 'bg-gradient-to-br from-indigo-50 to-blue-50/50 border-indigo-400 ring-2 ring-indigo-500/20 shadow-sm'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div
                  className={`p-2.5 rounded-xl ${
                    selectedDataset === 'behavior' ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  <Activity className="w-5 h-5" />
                </div>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                  Component 2
                </span>
              </div>
              <h3 className="font-bold text-slate-900 text-sm">Behavioral Telemetry</h3>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Weekly clickstream, video metrics (play, pause, rewinds, skips), and assignment delays.
              </p>
            </button>

            <button
              onClick={() => setSelectedDataset('academic')}
              className={`p-5 rounded-2xl border text-left transition relative overflow-hidden ${
                selectedDataset === 'academic'
                  ? 'bg-gradient-to-br from-purple-50 to-indigo-50/50 border-purple-400 ring-2 ring-purple-500/20 shadow-sm'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div
                  className={`p-2.5 rounded-xl ${
                    selectedDataset === 'academic' ? 'bg-purple-600 text-white' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  <GraduationCap className="w-5 h-5" />
                </div>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
                  Component 3
                </span>
              </div>
              <h3 className="font-bold text-slate-900 text-sm">Academic Records</h3>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Continuous assessment scores, quiz averages, attendance rates, and submission timeliness.
              </p>
            </button>

            <button
              onClick={() => setSelectedDataset('messages')}
              className={`p-5 rounded-2xl border text-left transition relative overflow-hidden ${
                selectedDataset === 'messages'
                  ? 'bg-gradient-to-br from-emerald-50 to-teal-50/50 border-emerald-400 ring-2 ring-emerald-500/20 shadow-sm'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div
                  className={`p-2.5 rounded-xl ${
                    selectedDataset === 'messages' ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  <MessageSquare className="w-5 h-5" />
                </div>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                  Component 1
                </span>
              </div>
              <h3 className="font-bold text-slate-900 text-sm">De-Identified Messages</h3>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Scrubbed discussion forum texts, latencies, and message lengths for affective NLP detection.
              </p>
            </button>
          </div>

          {/* Filter Bar & Export Actions */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2 text-xs font-bold text-slate-700 uppercase tracking-wider">
                <Filter className="w-4 h-4 text-indigo-600" />
                <span>Dataset Filters</span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => refetchExport()}
                  disabled={isLoadingExport || isRefetchingExport}
                  className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition"
                  title="Refresh Data"
                >
                  <RefreshCw className={`w-4 h-4 ${isRefetchingExport ? 'animate-spin' : ''}`} />
                </button>

                <button
                  onClick={handleDownloadCSV}
                  disabled={!exportData || !exportData.data || exportData.data.length === 0}
                  className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-bold transition disabled:opacity-50"
                >
                  <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
                  <span>Download CSV</span>
                </button>

                <button
                  onClick={handleDownloadJSON}
                  disabled={!exportData || !exportData.data || exportData.data.length === 0}
                  className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition shadow-sm disabled:opacity-50"
                >
                  <FileCode className="w-4 h-4" />
                  <span>Download JSON</span>
                </button>
              </div>
            </div>

            {/* Filter Inputs Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {/* Course */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                  Course
                </label>
                <select
                  value={selectedCourse}
                  onChange={(e) => setSelectedCourse(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                >
                  <option value="">All Courses</option>
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.id} — {c.title}
                    </option>
                  ))}
                </select>
              </div>

              {/* Week From */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                  From Week
                </label>
                <input
                  type="number"
                  min="0"
                  placeholder="e.g. 1"
                  value={weekFrom}
                  onChange={(e) => setWeekFrom(e.target.value === '' ? '' : Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              {/* Week To */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                  To Week
                </label>
                <input
                  type="number"
                  min="0"
                  placeholder="e.g. 12"
                  value={weekTo}
                  onChange={(e) => setWeekTo(e.target.value === '' ? '' : Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              {/* Student PID */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                  Student PID
                </label>
                <input
                  type="text"
                  placeholder="e.g. STU_xxxxxxxx"
                  value={pidFilter}
                  onChange={(e) => setPidFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              {/* Page Size */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                  Rows Limit
                </label>
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                >
                  <option value={25}>25 Rows</option>
                  <option value={50}>50 Rows</option>
                  <option value={100}>100 Rows</option>
                  <option value={200}>200 Rows</option>
                </select>
              </div>
            </div>
          </div>

          {/* Dataset Table View */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            {/* Table Header Info Bar */}
            <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs text-slate-600">
              <div className="flex items-center space-x-3">
                <span className="font-bold text-slate-800">
                  {exportData?.total ?? (exportData?.data?.length || 0)} Total Records Available
                </span>
                {exportData?.schema_version && (
                  <span className="px-2 py-0.5 rounded-full bg-slate-200 font-mono text-[10px] font-semibold text-slate-700">
                    Schema: {exportData.schema_version}
                  </span>
                )}
              </div>
              {exportData?.generated_at && (
                <span className="text-[11px] text-slate-400">
                  Generated: {new Date(exportData.generated_at).toLocaleTimeString()}
                </span>
              )}
            </div>

            {/* Table Content */}
            {isLoadingExport ? (
              <div className="p-12 text-center">
                <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-xs text-slate-500 font-medium">Querying and filtering pseudonymized data...</p>
              </div>
            ) : !exportData?.data || exportData.data.length === 0 ? (
              <div className="p-12 text-center text-slate-400 text-xs">
                No matching records found for the selected course and week range.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-500 uppercase font-bold text-[10px] tracking-wider">
                    {selectedDataset === 'behavior' && (
                      <tr>
                        <th className="px-4 py-3">PID</th>
                        <th className="px-4 py-3">Course</th>
                        <th className="px-4 py-3">Week</th>
                        <th className="px-4 py-3">Logins</th>
                        <th className="px-4 py-3">Session Mins</th>
                        <th className="px-4 py-3">Clicks</th>
                        <th className="px-4 py-3">Video Plays</th>
                        <th className="px-4 py-3">Video Completion</th>
                        <th className="px-4 py-3">Submissions</th>
                        <th className="px-4 py-3">Delay (hrs)</th>
                      </tr>
                    )}
                    {selectedDataset === 'academic' && (
                      <tr>
                        <th className="px-4 py-3">PID</th>
                        <th className="px-4 py-3">Course</th>
                        <th className="px-4 py-3">Week</th>
                        <th className="px-4 py-3">Attendance %</th>
                        <th className="px-4 py-3">Formative Avg</th>
                        <th className="px-4 py-3">Quiz Avg</th>
                        <th className="px-4 py-3">Midterm</th>
                        <th className="px-4 py-3">Submissions</th>
                        <th className="px-4 py-3">Delay Days</th>
                      </tr>
                    )}
                    {selectedDataset === 'messages' && (
                      <tr>
                        <th className="px-4 py-3">PID</th>
                        <th className="px-4 py-3">Course</th>
                        <th className="px-4 py-3">Week</th>
                        <th className="px-4 py-3">Type</th>
                        <th className="px-4 py-3">Message Clean Text</th>
                        <th className="px-4 py-3">Words</th>
                        <th className="px-4 py-3">Chars</th>
                        <th className="px-4 py-3">Timestamp</th>
                      </tr>
                    )}
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                    {selectedDataset === 'behavior' &&
                      (exportData.data as BehaviorWeeklyRecord[]).map((r, i) => (
                        <tr key={i} className="hover:bg-slate-50/50">
                          <td className="px-4 py-2.5 font-bold text-indigo-700">{r.pid}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.course_id}</td>
                          <td className="px-4 py-2.5 font-semibold text-slate-800">W{r.week_index}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.login_count}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.session_minutes.toFixed(1)}m</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.clicks}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.video_play_count}</td>
                          <td className="px-4 py-2.5 text-emerald-700 font-bold">
                            {(r.video_completion_pct * 100).toFixed(0)}%
                          </td>
                          <td className="px-4 py-2.5 text-slate-700">{r.submissions_count}</td>
                          <td className="px-4 py-2.5 text-slate-500">{r.avg_submission_delay_hours.toFixed(1)}h</td>
                        </tr>
                      ))}

                    {selectedDataset === 'academic' &&
                      (exportData.data as AcademicRecord[]).map((r, i) => (
                        <tr key={i} className="hover:bg-slate-50/50">
                          <td className="px-4 py-2.5 font-bold text-purple-700">{r.pid}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.course_id}</td>
                          <td className="px-4 py-2.5 font-semibold text-slate-800">W{r.week_index}</td>
                          <td className="px-4 py-2.5 text-slate-700">
                            {r.attendance_rate !== null && r.attendance_rate !== undefined
                              ? `${(r.attendance_rate * 100).toFixed(0)}%`
                              : '-'}
                          </td>
                          <td className="px-4 py-2.5 text-slate-700">{r.formative_score_avg?.toFixed(1) ?? '-'}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.quiz_score_avg?.toFixed(1) ?? '-'}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.midterm_score?.toFixed(1) ?? '-'}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.assignments_submitted_count}</td>
                          <td className="px-4 py-2.5 text-slate-500">{r.avg_submission_delay_days.toFixed(1)}d</td>
                        </tr>
                      ))}

                    {selectedDataset === 'messages' &&
                      (exportData.data as TextMessageRecord[]).map((r, i) => (
                        <tr key={i} className="hover:bg-slate-50/50">
                          <td className="px-4 py-2.5 font-bold text-emerald-700">{r.pid}</td>
                          <td className="px-4 py-2.5 text-slate-700">{r.course_id}</td>
                          <td className="px-4 py-2.5 font-semibold text-slate-800">W{r.week_index}</td>
                          <td className="px-4 py-2.5 uppercase text-[10px] text-slate-500 font-bold">
                            {r.source_type}
                          </td>
                          <td className="px-4 py-2.5 font-sans text-xs text-slate-800 max-w-md truncate" title={r.clean_text}>
                            {r.clean_text}
                          </td>
                          <td className="px-4 py-2.5 text-slate-600">{r.message_length_words}</td>
                          <td className="px-4 py-2.5 text-slate-600">{r.message_length_chars}</td>
                          <td className="px-4 py-2.5 text-slate-400 text-[10px]">
                            {new Date(r.timestamp).toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: WEEKLY AGGREGATION PIPELINE (FEATURE 20)                         */}
      {/* ========================================================================= */}
      {activeTab === 'pipeline' && (
        <div className="space-y-6">
          {/* Notification Feedback Banner */}
          {pipelineFeedback && (
            <div
              className={`p-4 rounded-2xl border flex items-center justify-between text-xs font-semibold animate-fade-in ${
                pipelineFeedback.type === 'success'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : 'bg-rose-50 border-rose-200 text-rose-800'
              }`}
            >
              <div className="flex items-center space-x-2">
                {pipelineFeedback.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                )}
                <span>{pipelineFeedback.message}</span>
              </div>
              <button
                onClick={() => setPipelineFeedback(null)}
                className="text-slate-400 hover:text-slate-600 text-xs"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Pipeline Overview Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Scheduler Status Card */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Scheduler State</span>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => refetchPipeline()}
                    className="p-1 text-slate-400 hover:text-slate-600 transition"
                    title="Refresh Pipeline Status"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isRefetchingPipeline ? 'animate-spin' : ''}`} />
                  </button>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-extrabold ${
                      pipelineStatus?.scheduler?.running
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                        pipelineStatus?.scheduler?.running ? 'bg-emerald-600 animate-pulse' : 'bg-amber-600'
                      }`}
                    />
                    {pipelineStatus?.scheduler?.running ? 'Active & Scheduled' : 'Idle / Standby'}
                  </span>
                </div>
              </div>
              <p className="text-2xl font-black text-slate-900 tracking-tight">
                {pipelineStatus?.scheduler?.job_count ?? 1} Recurring Job(s)
              </p>
              <p className="text-xs text-slate-400">
                Weekly telemetry aggregation automatically consolidates activity events every Sunday midnight UTC.
              </p>
            </div>

            {/* Last Execution Run Card */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Last Pipeline Run</span>
                <span className="text-[10px] font-mono font-bold text-slate-500">
                  {pipelineStatus?.latest_execution?.status?.toUpperCase() || 'COMPLETED'}
                </span>
              </div>
              <p className="text-2xl font-black text-indigo-600 tracking-tight">
                {pipelineStatus?.latest_execution?.behavior_records_created ?? 'Active'}
                <span className="text-xs font-normal text-slate-400 ml-1">records derived</span>
              </p>
              <p className="text-xs text-slate-400">
                Started:{' '}
                {pipelineStatus?.latest_execution?.started_at
                  ? new Date(pipelineStatus.latest_execution.started_at).toLocaleString()
                  : 'N/A'}
              </p>
            </div>

            {/* Server Timestamp Card */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Server Time (UTC)</span>
                <Clock className="w-4 h-4 text-slate-400" />
              </div>
              <p className="text-lg font-bold font-mono text-slate-800">
                {pipelineStatus?.server_time
                  ? new Date(pipelineStatus.server_time).toUTCString().slice(17, 25)
                  : '--:--:--'}
              </p>
              <p className="text-xs text-slate-400">
                Synchronized across all course modules, clickstreams, and Gradebook sessions.
              </p>
            </div>
          </div>

          {/* Trigger Aggregation Interactive Form */}
          <div className="bg-gradient-to-br from-slate-900 to-indigo-950 rounded-3xl p-6 sm:p-8 text-white shadow-xl space-y-6">
            <div>
              <div className="inline-flex items-center space-x-2 px-3 py-1 bg-indigo-500/20 text-indigo-300 rounded-xl text-xs font-bold mb-2">
                <Cpu className="w-3.5 h-3.5" />
                <span>Feature 20 Execution Controller</span>
              </div>
              <h2 className="text-xl font-bold tracking-tight">
                Manual Weekly Telemetry & Behavioral Aggregation
              </h2>
              <p className="text-xs text-slate-300 mt-1 max-w-xl">
                Consolidates raw student clickstream events, video playback interactions, and LMS assignment submissions into longitudinal weekly behavior records (`col.BEHAVIOR_WEEKLY`).
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              {/* Target Course */}
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5 uppercase tracking-wider">
                  Target Course
                </label>
                <select
                  value={pipelineCourse}
                  onChange={(e) => setPipelineCourse(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">All Active Courses (Batch)</option>
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.id} — {c.title}
                    </option>
                  ))}
                </select>
              </div>

              {/* Week Index */}
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5 uppercase tracking-wider">
                  Academic Week Index
                </label>
                <input
                  type="number"
                  min="0"
                  max="52"
                  value={pipelineWeek}
                  onChange={(e) => setPipelineWeek(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              {/* Execute Button */}
              <div className="flex items-end">
                <button
                  type="button"
                  onClick={() => triggerMutation.mutate()}
                  disabled={triggerMutation.isPending}
                  className="w-full inline-flex items-center justify-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg transition disabled:opacity-60"
                >
                  {triggerMutation.isPending ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Aggregating Telemetry...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 fill-current" />
                      <span>Execute Aggregation Job</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExportPipelinePage;
