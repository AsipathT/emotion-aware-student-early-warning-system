import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { coursesApi } from '../api/courses';
import { enrollmentsApi } from '../api/enrollments';
import {
  gradebookApi,
  CourseGradebookResponse,
  MyGradebookResponse,
} from '../api/gradebook';
import { useAuth } from '../hooks/useAuth';
import {
  Award,
  Download,
  BookOpen,
  AlertCircle,
  ExternalLink,
  ChevronDown,
  BarChart2,
} from 'lucide-react';

interface CourseOption {
  id: string;
  title: string;
}

export const GradebookPage: React.FC = () => {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const courseIdParam = searchParams.get('courseId');

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';
  const isStudent = user?.role === 'student';

  const [selectedCourseId, setSelectedCourseId] = useState<string>(courseIdParam || '');
  const [downloading, setDownloading] = useState(false);

  // 1. Fetch courses available to the user
  const { data: courses = [], isLoading: isLoadingCourses } = useQuery<CourseOption[]>({
    queryKey: ['availableCoursesForGradebook'],
    queryFn: async () => {
      if (isInstructor) {
        const fullCourses = await coursesApi.getCourses();
        return fullCourses.map((c) => ({ id: c.id, title: c.title }));
      } else {
        const enrollments = await enrollmentsApi.getMyEnrollments();
        return enrollments.map((enr) => ({
          id: enr.course_id,
          title: enr.course?.title || `Course ${enr.course_id.slice(0, 8)}`,
        }));
      }
    },
    enabled: !!user,
  });

  // Set default course when loaded
  useEffect(() => {
    if (!selectedCourseId && courses.length > 0) {
      setSelectedCourseId(courses[0].id);
    }
  }, [courses, selectedCourseId]);

  // Update query params when course changes
  const handleSelectCourse = (cid: string) => {
    setSelectedCourseId(cid);
    setSearchParams(cid ? { courseId: cid } : {});
  };

  // 2. Fetch instructor gradebook
  const {
    data: instructorGradebook,
    isLoading: isInstructorLoading,
    isError: isInstructorError,
    error: instructorError,
  } = useQuery<CourseGradebookResponse>({
    queryKey: ['courseGradebookOverview', selectedCourseId],
    queryFn: () => gradebookApi.getCourseGradebook(selectedCourseId),
    enabled: isInstructor && !!selectedCourseId,
  });

  // 3. Fetch student personal gradebook
  const {
    data: studentGradebook,
    isLoading: isStudentLoading,
    isError: isStudentError,
    error: studentError,
  } = useQuery<MyGradebookResponse>({
    queryKey: ['myGradebookOverview', selectedCourseId],
    queryFn: () => gradebookApi.getMyGradebook(selectedCourseId),
    enabled: isStudent && !!selectedCourseId,
  });

  const handleDownloadCsv = async () => {
    if (!selectedCourseId) return;
    try {
      setDownloading(true);
      await gradebookApi.downloadGradebookCsv(selectedCourseId);
    } catch (err) {
      console.error('Failed to download CSV', err);
    } finally {
      setDownloading(false);
    }
  };

  const selectedCourse = courses.find((c) => c.id === selectedCourseId);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-indigo-600 font-semibold text-xs tracking-wider uppercase mb-1">
            <Award className="w-4 h-4" />
            <span>Academic Performance Record</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Consolidated Gradebook</h1>
          <p className="text-slate-500 text-sm mt-1">
            Review assignment scores, quiz results, and weighted academic assessments.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {courses.length > 0 && (
            <div className="relative">
              <select
                value={selectedCourseId}
                onChange={(e) => handleSelectCourse(e.target.value)}
                className="appearance-none bg-slate-50 border border-slate-200 text-slate-800 text-sm rounded-xl py-2 pl-3 pr-8 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition"
              >
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          )}

          {isInstructor && selectedCourseId && (
            <>
              <button
                onClick={handleDownloadCsv}
                disabled={downloading}
                className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition disabled:opacity-50"
              >
                <Download className="w-4 h-4" />
                <span>{downloading ? 'Exporting...' : 'Export CSV'}</span>
              </button>

              <Link
                to={`/courses/${selectedCourseId}/gradebook`}
                className="inline-flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold shadow-xs transition"
              >
                <span>Full Gradebook View</span>
                <ExternalLink className="w-4 h-4" />
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Empty State when no courses available */}
      {courses.length === 0 && !isLoadingCourses && (
        <div className="bg-white p-12 text-center rounded-2xl border border-slate-200">
          <BookOpen className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-800">No Courses Enrolled or Found</h3>
          <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">
            You are not currently associated with any active courses. Check the Course Catalog to register.
          </p>
          <Link
            to="/courses"
            className="inline-block mt-4 px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition"
          >
            Browse Course Catalog
          </Link>
        </div>
      )}

      {/* Loading State */}
      {(isLoadingCourses || isInstructorLoading || isStudentLoading) && courses.length > 0 && (
        <div className="bg-white p-12 text-center rounded-2xl border border-slate-200">
          <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-500">Loading gradebook records...</p>
        </div>
      )}

      {/* Instructor View */}
      {isInstructor && selectedCourseId && !isInstructorLoading && instructorGradebook && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="font-bold text-slate-900 text-base">
                {selectedCourse?.title || 'Course'} — Class Gradebook
              </h2>
              <p className="text-xs text-slate-500">
                {instructorGradebook.students.length} enrolled students &bull; {instructorGradebook.items.length} graded items
              </p>
            </div>
          </div>

          {instructorGradebook.students.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-sm">
              No students or grades recorded yet for this course.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider">
                    <th className="p-3.5 font-semibold border-b border-slate-200">Student</th>
                    {instructorGradebook.items.map((item) => (
                      <th
                        key={item.key}
                        className="p-3.5 font-semibold text-right border-b border-slate-200 min-w-[120px]"
                      >
                        <div>{item.title}</div>
                        <div className="text-[10px] text-slate-400 font-normal">
                          Max: {item.max_score} | W: {item.weight}
                        </div>
                      </th>
                    ))}
                    <th className="p-3.5 font-semibold text-right border-b border-slate-200 text-indigo-700 min-w-[120px]">
                      Weighted Total
                    </th>
                    <th className="p-3.5 font-semibold text-right border-b border-slate-200 text-emerald-700 min-w-[100px]">
                      Score So Far
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {instructorGradebook.students.map((student) => {
                    const entriesMap = new Map(
                      student.entries.map((e) => [
                        `${e.item_type}:${e.item_id || e.title}`,
                        e.score,
                      ])
                    );

                    return (
                      <tr key={student.student_id} className="hover:bg-slate-50/70 transition">
                        <td className="p-3.5">
                          <div className="font-medium text-slate-900">{student.full_name}</div>
                          <div className="text-xs text-slate-400 font-mono">{student.email || student.student_id.slice(0, 8)}</div>
                        </td>
                        {instructorGradebook.items.map((item) => {
                          const score = entriesMap.get(item.key);
                          return (
                            <td key={item.key} className="p-3.5 text-right font-mono text-slate-700">
                              {score !== undefined ? (
                                <span className="font-semibold">{score}</span>
                              ) : (
                                <span className="text-slate-300">-</span>
                              )}
                            </td>
                          );
                        })}
                        <td className="p-3.5 text-right font-mono font-bold text-indigo-700">
                          {student.weighted_total}
                        </td>
                        <td className="p-3.5 text-right font-mono font-bold text-emerald-600">
                          {student.score_so_far}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Student View */}
      {isStudent && selectedCourseId && !isStudentLoading && studentGradebook && (
        <div className="space-y-6">
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center space-x-4">
              <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
                <BarChart2 className="w-6 h-6" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Weighted Score Total
                </p>
                <p className="text-2xl font-black text-slate-900">
                  {studentGradebook.weighted_total}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">Sum of weighted points achieved</p>
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center space-x-4">
              <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Score So Far
                </p>
                <p className="text-2xl font-black text-emerald-600">
                  {studentGradebook.score_so_far}%
                </p>
                <p className="text-xs text-slate-500 mt-0.5">Weighted average across completed items</p>
              </div>
            </div>
          </div>

          {/* Detailed Entries Table */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 border-b border-slate-100">
              <h2 className="font-bold text-slate-900 text-base">Graded Items & Assessments</h2>
              <p className="text-xs text-slate-500">Breakdown of assignments, quizzes, and course submissions</p>
            </div>

            {studentGradebook.entries.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                No grades recorded yet for this course. Complete upcoming assignments and quizzes to see your grades!
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider">
                      <th className="p-3.5 font-semibold border-b border-slate-200">Assessment</th>
                      <th className="p-3.5 font-semibold border-b border-slate-200">Type</th>
                      <th className="p-3.5 font-semibold text-right border-b border-slate-200">Score</th>
                      <th className="p-3.5 font-semibold text-right border-b border-slate-200">Max Score</th>
                      <th className="p-3.5 font-semibold text-right border-b border-slate-200">Weight</th>
                      <th className="p-3.5 font-semibold text-right border-b border-slate-200">Percentage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm">
                    {studentGradebook.entries.map((entry) => {
                      const pct = entry.max_score > 0 ? ((entry.score / entry.max_score) * 100).toFixed(1) : '0';
                      return (
                        <tr key={entry.id} className="hover:bg-slate-50/70 transition">
                          <td className="p-3.5 font-medium text-slate-900">{entry.title}</td>
                          <td className="p-3.5">
                            <span className="capitalize px-2 py-0.5 text-xs rounded-md bg-slate-100 text-slate-600 font-semibold">
                              {entry.item_type}
                            </span>
                          </td>
                          <td className="p-3.5 text-right font-mono font-semibold text-slate-900">{entry.score}</td>
                          <td className="p-3.5 text-right font-mono text-slate-500">{entry.max_score}</td>
                          <td className="p-3.5 text-right font-mono text-slate-500">{entry.weight}</td>
                          <td className="p-3.5 text-right font-mono font-bold text-indigo-600">{pct}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error State */}
      {(isInstructorError || isStudentError) && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-center space-x-2 text-sm">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          <span>
            {((instructorError as any)?.response?.data?.detail) ||
              ((studentError as any)?.response?.data?.detail) ||
              'Unable to load gradebook records for the selected course.'}
          </span>
        </div>
      )}
    </div>
  );
};
