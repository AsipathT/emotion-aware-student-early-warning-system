import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  adminApi,
  AdminCourseSummary,
  AdminPaginatedCoursesResponse,
} from '../../api/admin';
import { useAuth } from '../../hooks/useAuth';
import { PageHeader } from '../../components/admin/PageHeader';
import { StatusBadge } from '../../components/admin/StatusBadge';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import {
  Search,
  BookOpen,
  Users,
  ToggleLeft,
  ToggleRight,
  AlertCircle,
  X,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Edit2,
  Layers,
} from 'lucide-react';

export const AdminCoursesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const isAuditor = currentUser?.role === 'auditor';

  // Filters & Pagination
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [searchQuery, setSearchQuery] = useState('');
  const [publishFilter, setPublishFilter] = useState<string>('all');

  // Instructor Reassignment Modal
  const [reassignCourse, setReassignCourse] = useState<AdminCourseSummary | null>(null);
  const [newLecturerId, setNewLecturerId] = useState('');

  // Confirmation dialog state
  const [confirmState, setConfirmState] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    variant: 'danger' | 'warning' | 'primary';
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
    variant: 'primary',
  });

  // Query: Paginated Courses
  const {
    data: coursesData,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery<AdminPaginatedCoursesResponse>({
    queryKey: ['adminCourses', page, searchQuery, publishFilter],
    queryFn: () =>
      adminApi.getAdminCoursesPaginated({
        page,
        page_size: pageSize,
        q: searchQuery || undefined,
        is_published:
          publishFilter === 'published'
            ? true
            : publishFilter === 'draft'
            ? false
            : undefined,
      }),
  });

  // Query: Lecturers list for assignment modal
  const { data: usersData } = useQuery({
    queryKey: ['adminLecturersList'],
    queryFn: () => adminApi.getAdminUsersPaginated({ role: 'lecturer', page_size: 100 }),
  });
  const lecturers = usersData?.items || [];

  // Mutation: Publish / Unpublish Course
  const publishMutation = useMutation({
    mutationFn: ({ courseId, isPublished }: { courseId: string; isPublished: boolean }) =>
      adminApi.updateCoursePublishStatus(courseId, isPublished),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminCourses'] });
      queryClient.invalidateQueries({ queryKey: ['adminOverview'] });
    },
  });

  // Mutation: Reassign Lecturer
  const lecturerMutation = useMutation({
    mutationFn: ({ courseId, lecturerId }: { courseId: string; lecturerId: string }) =>
      adminApi.updateCourseLecturer(courseId, lecturerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminCourses'] });
      setReassignCourse(null);
      setNewLecturerId('');
    },
  });

  const handleTogglePublish = (course: AdminCourseSummary) => {
    if (isAuditor) return;
    const willPublish = !course.is_published;
    setConfirmState({
      isOpen: true,
      title: willPublish ? 'Publish Course to Catalog' : 'Unpublish Course to Draft',
      message: willPublish
        ? `Are you sure you want to publish "${course.title}"? Students will immediately be able to view and enrol in this course.`
        : `Are you sure you want to unpublish "${course.title}"? It will become hidden from catalog discovery.`,
      variant: willPublish ? 'primary' : 'warning',
      onConfirm: () => {
        publishMutation.mutate({
          courseId: course.course_id || course.id,
          isPublished: willPublish,
        });
        setConfirmState((prev) => ({ ...prev, isOpen: false }));
      },
    });
  };

  const handleOpenReassignModal = (course: AdminCourseSummary) => {
    if (isAuditor) return;
    setReassignCourse(course);
    setNewLecturerId(course.lecturer_id || '');
  };

  const handleConfirmReassign = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reassignCourse || !newLecturerId) return;
    lecturerMutation.mutate({
      courseId: reassignCourse.course_id || reassignCourse.id,
      lecturerId: newLecturerId,
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Courses Oversight"
        description="Catalog visibility, instructor assignments, and live student enrolment counts."
        actions={
          isAuditor ? (
            <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded-full border border-indigo-200">
              Read-Only Auditor View
            </span>
          ) : undefined
        }
      />

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="flex flex-1 w-full gap-3 flex-wrap sm:flex-nowrap">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by title, description or code..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setPage(1);
                }}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Publication Filter */}
          <select
            value={publishFilter}
            onChange={(e) => {
              setPublishFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700"
          >
            <option value="all">All Statuses</option>
            <option value="published">Published Only</option>
            <option value="draft">Drafts Only</option>
          </select>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center px-3 py-2 text-sm text-slate-600 hover:text-indigo-600 border border-slate-300 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
          title="Refresh table"
        >
          <RefreshCw className={`w-4 h-4 mr-1.5 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Course Code & Title
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Instructor
                </th>
                <th className="px-6 py-3 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Enrolments
                </th>
                <th className="px-6 py-3 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Modules
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500" />
                    Loading academic courses...
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-rose-500">
                    <AlertCircle className="w-6 h-6 mx-auto mb-2" />
                    Failed to load courses. Please check your network and permissions.
                  </td>
                </tr>
              ) : !coursesData?.items || coursesData.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    <BookOpen className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    No courses found matching the search criteria.
                  </td>
                </tr>
              ) : (
                coursesData.items.map((course) => (
                  <tr key={course.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold text-slate-900">{course.title}</span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                            {course.course_id}
                          </span>
                          {course.description && (
                            <span className="text-xs text-slate-500 truncate max-w-xs">
                              {course.description}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {course.lecturer_name ? (
                        <div className="flex items-center gap-2">
                          <div>
                            <p className="text-sm font-medium text-slate-800">{course.lecturer_name}</p>
                            <p className="text-xs text-slate-400">{course.lecturer_email || 'No email'}</p>
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded font-medium">
                          Unassigned
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700">
                        <Users className="w-3.5 h-3.5" />
                        {course.enrolment_count}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
                        <Layers className="w-3.5 h-3.5" />
                        {course.module_count}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={course.is_published ? 'published' : 'draft'} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="inline-flex items-center gap-2">
                        {/* Reassign Lecturer */}
                        <button
                          onClick={() => handleOpenReassignModal(course)}
                          disabled={isAuditor}
                          className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-40"
                          title="Reassign Instructor"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>

                        {/* Toggle Publish */}
                        <button
                          onClick={() => handleTogglePublish(course)}
                          disabled={isAuditor || publishMutation.isPending}
                          className={`p-1.5 rounded-lg transition-colors disabled:opacity-40 ${
                            course.is_published
                              ? 'text-emerald-600 hover:bg-emerald-50'
                              : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
                          }`}
                          title={course.is_published ? 'Unpublish Course' : 'Publish Course'}
                        >
                          {course.is_published ? (
                            <ToggleRight className="w-6 h-6" />
                          ) : (
                            <ToggleLeft className="w-6 h-6" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {coursesData && coursesData.total_pages > 1 && (
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
            <p className="text-sm text-slate-600">
              Showing <span className="font-medium">{(page - 1) * pageSize + 1}</span> to{' '}
              <span className="font-medium">
                {Math.min(page * pageSize, coursesData.total)}
              </span>{' '}
              of <span className="font-medium">{coursesData.total}</span> courses
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 border border-slate-300 rounded-lg text-slate-600 hover:bg-white disabled:opacity-40 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm font-medium text-slate-700 px-2">
                Page {page} of {coursesData.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(coursesData.total_pages, p + 1))}
                disabled={page === coursesData.total_pages}
                className="p-1.5 border border-slate-300 rounded-lg text-slate-600 hover:bg-white disabled:opacity-40 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Reassign Lecturer Modal */}
      {reassignCourse && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-lg font-semibold text-slate-900">Reassign Course Instructor</h3>
              <button
                onClick={() => setReassignCourse(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleConfirmReassign} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Target Course</label>
                <p className="text-sm font-semibold text-slate-800">{reassignCourse.title}</p>
                <p className="text-xs text-slate-400">{reassignCourse.course_id}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Select Instructor
                </label>
                <select
                  value={newLecturerId}
                  onChange={(e) => setNewLecturerId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                >
                  <option value="">-- Choose active lecturer --</option>
                  {lecturers.map((lec) => (
                    <option key={lec.id} value={lec.id}>
                      {lec.full_name} ({lec.email})
                    </option>
                  ))}
                </select>
              </div>

              {lecturerMutation.isError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>Failed to reassign instructor. Please try again.</span>
                </div>
              )}

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setReassignCourse(null)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={lecturerMutation.isPending || !newLecturerId}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {lecturerMutation.isPending ? 'Saving...' : 'Assign Instructor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmState.isOpen}
        title={confirmState.title}
        message={confirmState.message}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState((prev) => ({ ...prev, isOpen: false }))}
        variant={confirmState.variant}
        isLoading={publishMutation.isPending}
      />
    </div>
  );
};
