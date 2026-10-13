import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { staffAffectiveApi, StaffStudentSummaryItem } from '../api/staffAffective';
import { coursesApi, CourseResponse } from '../api/courses';
import { StaffTabs } from '../components/staff/StaffTabs';
import {
  ShieldCheck,
  Filter,
  AlertCircle,
  ChevronRight,
  MessageSquare,
  Sparkles,
  TrendingUp,
} from 'lucide-react';

const CLASS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  exam_anxiety: { bg: 'bg-amber-50', text: 'text-amber-800', border: 'border-amber-200' },
  conceptual_confusion: { bg: 'bg-purple-50', text: 'text-purple-800', border: 'border-purple-200' },
  academic_helplessness: { bg: 'bg-rose-50', text: 'text-rose-800', border: 'border-rose-200' },
  course_frustration: { bg: 'bg-orange-50', text: 'text-orange-800', border: 'border-orange-200' },
  motivation_erosion: { bg: 'bg-indigo-50', text: 'text-indigo-800', border: 'border-indigo-200' },
};

const CLASS_LABELS: Record<string, string> = {
  exam_anxiety: 'Exam Anxiety',
  conceptual_confusion: 'Conceptual Confusion',
  academic_helplessness: 'Academic Helplessness',
  course_frustration: 'Course Frustration',
  motivation_erosion: 'Motivation Erosion',
};

export const StaffAffectivePage: React.FC = () => {
  const navigate = useNavigate();

  const [courseFilter, setCourseFilter] = useState<string>('');
  const [weekFilter, setWeekFilter] = useState<string>('');
  const [page, setPage] = useState<number>(1);

  // Load available courses for the dropdown filter
  const { data: courses = [] } = useQuery<CourseResponse[]>({
    queryKey: ['courses'],
    queryFn: coursesApi.getCourses,
  });

  // Load affective student summaries
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['staffAffectiveStudents', courseFilter, weekFilter, page],
    queryFn: () =>
      staffAffectiveApi.getStudents({
        course_id: courseFilter || undefined,
        week_index: weekFilter !== '' ? parseInt(weekFilter, 10) : undefined,
        page,
        page_size: 20,
      }),
  });

  const students = data?.items || [];
  const totalPages = data?.total_pages || 1;

  const handleRowClick = (student: StaffStudentSummaryItem) => {
    navigate(`/staff/affective/${student.pid}?course_id=${encodeURIComponent(student.course_id)}`);
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
              Component 1 (Affective State Detection) distress indicators, XAI root-cause attributions, and reflection monitoring.
            </p>
          </div>
          <div className="text-xs text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-indigo-600" />
            Decision-support only • Privacy preserved
          </div>
        </div>

        {/* Staff Workspace Navigation Tabs */}
        <StaffTabs />
      </div>

      {/* Filters Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm mb-6">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
          <div className="flex-1 flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Filter className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <select
                value={courseFilter}
                onChange={(e) => {
                  setCourseFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full pl-9 pr-8 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700"
              >
                <option value="">All Courses</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title} ({c.id})
                  </option>
                ))}
              </select>
            </div>

            <div className="w-full sm:w-48">
              <select
                value={weekFilter}
                onChange={(e) => {
                  setWeekFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700"
              >
                <option value="">Latest Observation</option>
                {[...Array(15).keys()].map((w) => (
                  <option key={w} value={w}>
                    Week {w + 1} (Index {w})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {(courseFilter || weekFilter !== '') && (
            <button
              onClick={() => {
                setCourseFilter('');
                setWeekFilter('');
                setPage(1);
              }}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium px-2 py-1 self-center"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div className="mb-6 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-semibold">Failed to load student affective records</h3>
            <p className="text-sm text-rose-700 mt-0.5">
              {(error as any)?.response?.data?.detail || 'An unexpected error occurred while communicating with the backend.'}
            </p>
            <button
              onClick={() => refetch()}
              className="mt-2 text-xs font-semibold underline text-rose-900 hover:text-rose-950"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-600 border-t-transparent mb-3" />
          <p className="text-sm text-slate-500">Loading consented student distress profiles...</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && students.length === 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 shadow-sm text-center">
          <Sparkles className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-900">No affective records found</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
            No affective records matching the selected filters are currently present for consenting students.
          </p>
        </div>
      )}

      {/* Student summaries list */}
      {!isLoading && !isError && students.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/75 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Student (PID)</th>
                  <th className="py-3 px-4">Course</th>
                  <th className="py-3 px-4">Observed Week</th>
                  <th className="py-3 px-4">Primary Distress Signal</th>
                  <th className="py-3 px-4">Distress Score</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Scrubbed Msgs</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {students.map((student) => {
                  const style = CLASS_COLORS[student.dominant_class] || {
                    bg: 'bg-slate-100',
                    text: 'text-slate-800',
                    border: 'border-slate-200',
                  };
                  const label = CLASS_LABELS[student.dominant_class] || student.dominant_class;

                  return (
                    <tr
                      key={`${student.pid}-${student.course_id}-${student.week_index}`}
                      onClick={() => handleRowClick(student)}
                      className="hover:bg-slate-50/80 cursor-pointer transition"
                    >
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-900">
                        {student.pid}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 font-medium">
                        {student.course_id}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600">
                        Week {student.week_index + 1}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${style.bg} ${style.text} ${style.border}`}
                        >
                          {label}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-slate-100 rounded-full h-2 overflow-hidden">
                            <div
                              className="bg-indigo-600 h-2 rounded-full"
                              style={{ width: `${Math.min(100, Math.max(0, student.dominant_score * 100))}%` }}
                            />
                          </div>
                          <span className="text-xs font-semibold text-slate-700">
                            {student.dominant_score.toFixed(2)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 text-xs">
                        {(student.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="py-3.5 px-4 text-slate-600">
                        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                          <MessageSquare className="w-3.5 h-3.5" />
                          {student.message_count}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <span className="inline-flex items-center text-xs font-semibold text-indigo-600 hover:text-indigo-800">
                          Inspect <ChevronRight className="w-4 h-4 ml-0.5" />
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="p-4 border-t border-slate-200 flex items-center justify-between text-sm">
              <span className="text-slate-500 text-xs">
                Page {page} of {totalPages} ({data?.total_count} total students)
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
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
