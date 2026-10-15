import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coursesApi, CourseResponse } from '../api/courses';
import {
  assessmentApi,
  Assignment,
  AssignmentCreatePayload,
  AssignmentUpdatePayload,
  AssignmentSubmission,
} from '../api/assessment';
import { useAuth } from '../hooks/useAuth';
import {
  FileText,
  Plus,
  ArrowLeft,
  Calendar,
  Clock,
  Award,
  Percent,
  CheckCircle2,
  AlertCircle,
  Edit2,
  Trash2,
  ChevronRight,
  X,
  FileCheck,
} from 'lucide-react';

export const CourseAssignmentsPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';
  const isStudent = user?.role === 'student';

  // Modal states for Lecturer: Create & Edit
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingAssignment, setEditingAssignment] = useState<Assignment | null>(null);

  // Form states
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueAt, setDueAt] = useState('');
  const [maxScore, setMaxScore] = useState<number>(100);
  const [weight, setWeight] = useState<number>(0.1);
  const [isPublished, setIsPublished] = useState<boolean>(true);
  const [formError, setFormError] = useState<string | null>(null);

  // Notification banners
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // 1. Fetch course details
  const { data: course } = useQuery<CourseResponse>({
    queryKey: ['course', courseId],
    queryFn: () => coursesApi.getCourseById(courseId!),
    enabled: !!courseId,
  });

  // 2. Fetch assignments
  const {
    data: assignments = [],
    isLoading: isAssignmentsLoading,
    isError: isAssignmentsError,
    error: assignmentsError,
  } = useQuery<Assignment[]>({
    queryKey: ['assignments', courseId],
    queryFn: () => assessmentApi.getAssignments(courseId!),
    enabled: !!courseId,
  });

  // 3. For students: fetch student's submissions across assignments to display status badge
  const { data: studentSubmissions = {} } = useQuery<Record<string, AssignmentSubmission | null>>({
    queryKey: ['studentSubmissionsMap', courseId, assignments.map((a) => a.id).join(',')],
    queryFn: async () => {
      const results: Record<string, AssignmentSubmission | null> = {};
      await Promise.all(
        assignments.map(async (a) => {
          try {
            const sub = await assessmentApi.getMySubmission(courseId!, a.id);
            results[a.id] = sub;
          } catch {
            results[a.id] = null;
          }
        })
      );
      return results;
    },
    enabled: isStudent && assignments.length > 0,
  });

  // 4. Create Assignment Mutation
  const createMutation = useMutation({
    mutationFn: (payload: AssignmentCreatePayload) =>
      assessmentApi.createAssignment(courseId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments', courseId] });
      setIsCreateOpen(false);
      resetForm();
      setSuccessBanner('Assignment created successfully.');
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || 'Failed to create assignment.');
    },
  });

  // 5. Update Assignment Mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AssignmentUpdatePayload }) =>
      assessmentApi.updateAssignment(courseId!, id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments', courseId] });
      setEditingAssignment(null);
      resetForm();
      setSuccessBanner('Assignment updated successfully.');
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || 'Failed to update assignment.');
    },
  });

  // 6. Delete Assignment Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => assessmentApi.deleteAssignment(courseId!, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments', courseId] });
      setSuccessBanner('Assignment removed.');
    },
    onError: (err: any) => {
      setErrorBanner(err.response?.data?.detail || 'Failed to delete assignment.');
    },
  });

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setDueAt('');
    setMaxScore(100);
    setWeight(0.1);
    setIsPublished(true);
    setFormError(null);
  };

  const handleOpenCreate = () => {
    resetForm();
    setIsCreateOpen(true);
  };

  const handleOpenEdit = (a: Assignment) => {
    setEditingAssignment(a);
    setTitle(a.title);
    setDescription(a.description || '');
    setDueAt(a.due_at ? new Date(a.due_at).toISOString().slice(0, 16) : '');
    setMaxScore(a.max_score);
    setWeight(a.weight);
    setIsPublished(a.is_published);
    setFormError(null);
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setFormError('Assignment title is required.');
      return;
    }
    createMutation.mutate({
      title: title.trim(),
      description: description.trim() || null,
      due_at: dueAt ? new Date(dueAt).toISOString() : null,
      max_score: Number(maxScore),
      weight: Number(weight),
      is_published: isPublished,
    });
  };

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAssignment) return;
    if (!title.trim()) {
      setFormError('Assignment title is required.');
      return;
    }
    updateMutation.mutate({
      id: editingAssignment.id,
      payload: {
        title: title.trim(),
        description: description.trim() || null,
        due_at: dueAt ? new Date(dueAt).toISOString() : null,
        max_score: Number(maxScore),
        weight: Number(weight),
        is_published: isPublished,
      },
    });
  };

  const handleDelete = (id: string, aTitle: string) => {
    if (window.confirm(`Are you sure you want to delete assignment "${aTitle}"?`)) {
      deleteMutation.mutate(id);
    }
  };

  const getStudentStatusBadge = (assignment: Assignment) => {
    const sub = studentSubmissions[assignment.id];
    const isPastDue = assignment.due_at && new Date() > new Date(assignment.due_at);

    if (sub) {
      if (sub.score !== null && sub.score !== undefined) {
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" />
            Graded: {sub.score} / {assignment.max_score}
          </span>
        );
      }
      if (sub.is_late) {
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-orange-100 text-orange-800 border border-orange-200">
            <Clock className="w-3.5 h-3.5 mr-1 text-orange-600" />
            Submitted Late ({sub.delay_days}d)
          </span>
        );
      }
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
          <FileCheck className="w-3.5 h-3.5 mr-1 text-blue-600" />
          Submitted
        </span>
      );
    }

    if (isPastDue) {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
          <AlertCircle className="w-3.5 h-3.5 mr-1 text-rose-600" />
          Past Due (Unsubmitted)
        </span>
      );
    }

    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
        Not Submitted
      </span>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to={`/courses/${courseId}`}
          className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-indigo-600 transition group"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5 group-hover:-translate-x-0.5 transition" />
          Back to Course Overview
        </Link>
        {isInstructor && (
          <button
            onClick={handleOpenCreate}
            className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-sm hover:shadow transition"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Assignment
          </button>
        )}
      </div>

      {/* Header Banner */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-sm relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="inline-flex items-center px-2.5 py-1 bg-indigo-50 border border-indigo-100 rounded-lg text-indigo-700 text-xs font-semibold">
              <FileText className="w-3.5 h-3.5 mr-1.5" />
              Feature 10: Course Assignments
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              {course?.title || 'Course'} Assignments
            </h1>
            <p className="text-sm text-slate-500">
              {isInstructor
                ? 'Create, manage, and grade learning assignments and student submissions.'
                : 'Review course tasks, submit your deliverables, and track feedback.'}
            </p>
          </div>
          <div className="flex items-center space-x-3 text-xs text-slate-600 font-medium">
            <span className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl">
              {assignments.length} Total Assignments
            </span>
          </div>
        </div>
      </div>

      {/* Toast Banners */}
      {successBanner && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-800 text-sm flex items-center justify-between">
          <div className="flex items-center">
            <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-600" />
            <span>{successBanner}</span>
          </div>
          <button onClick={() => setSuccessBanner(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {errorBanner && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-sm flex items-center justify-between">
          <div className="flex items-center">
            <AlertCircle className="w-4 h-4 mr-2 text-rose-600" />
            <span>{errorBanner}</span>
          </div>
          <button onClick={() => setErrorBanner(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Content Loading / Empty / List */}
      {isAssignmentsLoading ? (
        <div className="py-20 text-center space-y-3">
          <div className="w-8 h-8 border-3 border-indigo-600/30 border-t-indigo-600 rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-400">Loading assignments...</p>
        </div>
      ) : isAssignmentsError ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-rose-800">
          <AlertCircle className="w-8 h-8 mx-auto text-rose-600 mb-2" />
          <h3 className="font-bold text-sm">Failed to load assignments</h3>
          <p className="text-xs mt-1">{(assignmentsError as any)?.response?.data?.detail || 'Network error'}</p>
        </div>
      ) : assignments.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-3xl border border-slate-200/80 p-8 shadow-sm">
          <div className="inline-flex p-4 bg-indigo-50 text-indigo-600 rounded-2xl mb-3">
            <FileText className="w-8 h-8" />
          </div>
          <h3 className="font-bold text-slate-900 text-base">No assignments available</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            {isInstructor
              ? 'Get started by creating the first assignment for your students.'
              : 'There are no published assignments for this course yet.'}
          </p>
          {isInstructor && (
            <button
              onClick={handleOpenCreate}
              className="mt-4 inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition"
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Create First Assignment
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {assignments.map((assignment) => (
            <div
              key={assignment.id}
              className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm hover:border-indigo-300 hover:shadow-md transition flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-2 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-bold text-slate-900">
                    <Link
                      to={`/courses/${courseId}/assignments/${assignment.id}`}
                      className="hover:text-indigo-600 transition"
                    >
                      {assignment.title}
                    </Link>
                  </h3>
                  {isInstructor && (
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        assignment.is_published
                          ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                          : 'bg-slate-100 text-slate-600 border border-slate-200'
                      }`}
                    >
                      {assignment.is_published ? 'Published' : 'Draft'}
                    </span>
                  )}
                  {isStudent && getStudentStatusBadge(assignment)}
                </div>

                {assignment.description && (
                  <p className="text-xs text-slate-600 line-clamp-2 max-w-2xl">
                    {assignment.description}
                  </p>
                )}

                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
                  <span className="flex items-center">
                    <Calendar className="w-3.5 h-3.5 mr-1 text-slate-400" />
                    Due:{' '}
                    {assignment.due_at
                      ? new Date(assignment.due_at).toLocaleString()
                      : 'No deadline set'}
                  </span>
                  <span className="flex items-center">
                    <Award className="w-3.5 h-3.5 mr-1 text-indigo-500" />
                    Max: {assignment.max_score} pts
                  </span>
                  <span className="flex items-center">
                    <Percent className="w-3.5 h-3.5 mr-1 text-indigo-500" />
                    Weight: {(assignment.weight * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center space-x-2 pt-2 md:pt-0">
                {isInstructor && (
                  <>
                    <button
                      onClick={() => handleOpenEdit(assignment)}
                      className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition"
                      title="Edit Assignment"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(assignment.id, assignment.title)}
                      className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition"
                      title="Delete Assignment"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </>
                )}

                <Link
                  to={`/courses/${courseId}/assignments/${assignment.id}`}
                  className="inline-flex items-center px-4 py-2 bg-slate-100 hover:bg-indigo-600 hover:text-white text-slate-700 font-semibold text-xs rounded-xl transition group"
                >
                  <span>{isInstructor ? 'Submissions & Grade' : 'Open Assignment'}</span>
                  <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-0.5 transition" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Create or Edit Assignment */}
      {(isCreateOpen || editingAssignment) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-slate-100 space-y-6 relative max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <h3 className="text-lg font-bold text-slate-900">
                {editingAssignment ? 'Edit Assignment' : 'Create New Assignment'}
              </h3>
              <button
                onClick={() => {
                  setIsCreateOpen(false);
                  setEditingAssignment(null);
                }}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-center">
                <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form
              onSubmit={editingAssignment ? handleEditSubmit : handleCreateSubmit}
              className="space-y-4 text-xs font-medium"
            >
              <div>
                <label className="block text-slate-700 mb-1 font-semibold">Title *</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Lab 1: Relational Database Schema"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-600 transition"
                />
              </div>

              <div>
                <label className="block text-slate-700 mb-1 font-semibold">Description & Instructions</label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Provide instructions, rubric guidelines, and required deliverables..."
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-600 transition"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 mb-1 font-semibold">Due Date & Time</label>
                  <input
                    type="datetime-local"
                    value={dueAt}
                    onChange={(e) => setDueAt(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-600 transition"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 mb-1 font-semibold">Max Score</label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={maxScore}
                    onChange={(e) => setMaxScore(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-600 transition"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 mb-1 font-semibold">Grade Weight (0.0 to 1.0)</label>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={weight}
                    onChange={(e) => setWeight(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-600 transition"
                  />
                </div>
                <div className="flex items-center pt-5">
                  <label className="inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isPublished}
                      onChange={(e) => setIsPublished(e.target.checked)}
                      className="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4 mr-2"
                    />
                    <span className="text-slate-700 font-semibold">Publish immediately</span>
                  </label>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => {
                    setIsCreateOpen(false);
                    setEditingAssignment(null);
                  }}
                  className="px-4 py-2 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-sm transition disabled:opacity-60"
                >
                  {createMutation.isPending || updateMutation.isPending
                    ? 'Saving...'
                    : editingAssignment
                    ? 'Save Changes'
                    : 'Create Assignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
