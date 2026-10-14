/**
 * src/pages/StaffStudentsPage.tsx
 *
 * Feature 31: Staff Student Overview & Triage List (Component 4).
 * Combines C1 (affective), C2 (engagement trajectory), and C3 (dropout risk).
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Users,
  ShieldCheck,
  TrendingUp,
  Filter,
  ChevronRight,
  AlertTriangle,
  Loader2,
  Sparkles,
  ArrowUpDown,
  RefreshCw,
} from 'lucide-react';
import { StaffTabs } from '../components/staff/StaffTabs';
import { staffStudentsApi, StaffStudentOverviewItem } from '../api/staffStudents';
import { coursesApi, CourseResponse } from '../api/courses';

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

export const StaffStudentsPage: React.FC = () => {
  const navigate = useNavigate();

  const [courseFilter, setCourseFilter] = useState<string>('');
  const [tierFilter, setTierFilter] = useState<string>('');
  const [page, setPage] = useState<number>(1);

  // Load courses for filter dropdown
  const { data: courses = [] } = useQuery<CourseResponse[]>({
    queryKey: ['courses'],
    queryFn: coursesApi.getCourses,
  });

  // Load student risk overview
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['staffStudentsOverview', courseFilter, tierFilter, page],
    queryFn: () =>
      staffStudentsApi.getStudents({
        course_id: courseFilter || undefined,
        tier: tierFilter || undefined,
        page,
        page_size: 20,
      }),
  });

  const students = data?.items || [];
  const totalCount = data?.total_count || 0;
  const totalPages = data?.total_pages || 1;

  const handleRowClick = (student: StaffStudentOverviewItem) => {
    navigate(
      `/staff/students/${encodeURIComponent(student.pid)}?course_id=${encodeURIComponent(
        student.course_id
      )}`
    );
  };

  const renderTierChip = (tier: string) => {
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

  const renderTrajectoryChip = (trajectory: string) => {
    const key = trajectory.toLowerCase();
    const style = TRAJECTORY_STYLES[key] || {
      bg: 'bg-slate-50',
      text: 'text-slate-600',
      border: 'border-slate-200',
    };
    return (
      <span
        className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium border ${style.bg} ${style.text} ${style.border}`}
      >
        {trajectory.replace(/_/g, ' ')}
      </span>
    );
  };

  const getErrorMessage = (err: any): string => {
    return (
      err?.response?.data?.detail ||
      err?.message ||
      'Unable to load student risk triage overview.'
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
              Component 4 Multi-Modal Student Context — Unified early warning triage combining affective state (C1), engagement trajectory (C2), and dropout risk (C3).
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

      {/* Filter and Control Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-slate-600 text-sm font-medium mr-1">
              <Filter className="w-4 h-4 text-indigo-600" />
              <span>Filters:</span>
            </div>

            {/* Course Filter */}
            <div className="min-w-[200px]">
              <select
                id="course-filter-select"
                value={courseFilter}
                onChange={(e) => {
                  setCourseFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full text-sm border-slate-200 rounded-lg px-3 py-2 bg-slate-50/50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
              >
                <option value="">All Courses</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title} ({c.id})
                  </option>
                ))}
              </select>
            </div>

            {/* Risk Tier Filter */}
            <div className="min-w-[150px]">
              <select
                id="tier-filter-select"
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

            {(courseFilter || tierFilter) && (
              <button
                type="button"
                onClick={() => {
                  setCourseFilter('');
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
              Showing <strong className="text-slate-800">{students.length}</strong> of{' '}
              <strong className="text-slate-800">{totalCount}</strong> students
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
            Synthesizing multi-modal student risk analytics...
          </p>
        </div>
      ) : isError ? (
        <div className="bg-rose-50 rounded-2xl border border-rose-200 p-6 text-rose-800 shadow-sm">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-sm">Failed to load student risk list</h3>
              <p className="text-xs text-rose-700 mt-1">{getErrorMessage(error)}</p>
            </div>
          </div>
        </div>
      ) : students.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No student analytics found</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
            {courseFilter || tierFilter
              ? 'No consenting students matched the selected filters. Try broadening your criteria.'
              : 'No students currently have ingested risk assessments or active research consent.'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50/75 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-3.5">
                    Pseudonymous ID
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Course
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Week
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    <span className="flex items-center gap-1">
                      Risk Tier & Score
                      <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
                    </span>
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Trajectory (C2)
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Affective Distress (C1)
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-right">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {students.map((student) => (
                  <tr
                    key={`${student.pid}-${student.course_id}`}
                    onClick={() => handleRowClick(student)}
                    className="hover:bg-indigo-50/40 cursor-pointer transition group"
                  >
                    <td className="px-6 py-4 font-mono font-medium text-slate-800 text-xs">
                      <span className="bg-slate-100 px-2 py-1 rounded text-slate-700 group-hover:bg-white group-hover:text-indigo-700 transition">
                        {student.pid}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-600 font-medium text-xs">
                      {student.course_id}
                    </td>
                    <td className="px-6 py-4 text-slate-500 text-xs">
                      W{student.week_index}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        {renderTierChip(student.risk_tier)}
                        <span className="font-mono text-xs text-slate-600">
                          {student.risk_score !== null
                            ? (student.risk_score * 100).toFixed(0) + '%'
                            : '—'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {renderTrajectoryChip(student.trajectory_label)}
                    </td>
                    <td className="px-6 py-4 text-xs">
                      {student.dominant_distress_class !== 'none' ? (
                        <span className="inline-flex items-center gap-1 text-slate-700">
                          <Sparkles className="w-3 h-3 text-indigo-500" />
                          <span className="capitalize">
                            {student.dominant_distress_class.replace(/_/g, ' ')}
                          </span>
                        </span>
                      ) : (
                        <span className="text-slate-400">None detected</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="inline-flex items-center text-xs font-semibold text-indigo-600 group-hover:text-indigo-800 transition">
                        View Context
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
