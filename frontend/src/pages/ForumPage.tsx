import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { forumApi, ThreadListItem, ThreadCreatePayload } from '../api/forum';
import { coursesApi, CourseResponse } from '../api/courses';
import { useAuth } from '../hooks/useAuth';
import { formatRelativeTime } from '../utils/time';
import {
  ArrowLeft,
  MessageSquare,
  Plus,
  Search,
  Pin,
  Lock,
  AlertCircle,
  X,
  CheckCircle2,
  MessagesSquare,
} from 'lucide-react';

export const ForumPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const canWrite =
    user?.role === 'student' || user?.role === 'lecturer' || user?.role === 'admin';

  // Search state
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce search input by 400ms
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newBody, setNewBody] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  // Toast
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  useEffect(() => {
    if (successMessage) {
      const t = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(t);
    }
  }, [successMessage]);

  // Queries
  const { data: course } = useQuery<CourseResponse>({
    queryKey: ['course', courseId],
    queryFn: () => coursesApi.getCourseById(courseId!),
    enabled: !!courseId,
  });

  const {
    data: threads = [],
    isLoading,
    isError,
    error,
  } = useQuery<ThreadListItem[]>({
    queryKey: ['forumThreads', courseId, debouncedSearch],
    queryFn: () =>
      forumApi.getThreads(courseId!, {
        search: debouncedSearch || undefined,
        limit: 100,
      }),
    enabled: !!courseId,
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: (payload: ThreadCreatePayload) =>
      forumApi.createThread(courseId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forumThreads', courseId] });
      setIsModalOpen(false);
      setNewTitle('');
      setNewBody('');
      setFormError(null);
      setSuccessMessage('Thread created successfully.');
    },
    onError: (err: any) => {
      setFormError(
        err.response?.data?.detail || 'Failed to create thread. Please try again.'
      );
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!newTitle.trim() || !newBody.trim()) {
      setFormError('Title and body are required.');
      return;
    }
    createMutation.mutate({ title: newTitle.trim(), body: newBody.trim() });
  };

  // Helpers
  const roleChipClasses = (role: string) => {
    switch (role) {
      case 'lecturer':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'admin':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'counsellor':
        return 'bg-teal-50 text-teal-700 border-teal-200';
      default:
        return 'bg-indigo-50 text-indigo-700 border-indigo-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Success toast */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between text-emerald-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <span className="font-medium">{successMessage}</span>
          </div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-600 hover:text-emerald-800 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Back link */}
      <div>
        <Link
          to={`/courses/${courseId}`}
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-indigo-600 transition group"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5 group-hover:-translate-x-1 transition" />
          Back to Course
        </Link>
      </div>

      {/* Header banner */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-2">
            <span className="inline-flex items-center px-2.5 py-0.5 bg-indigo-50 text-indigo-700 rounded-full text-xs font-semibold uppercase tracking-wider">
              <MessagesSquare className="w-3 h-3 mr-1" />
              Discussion Forum
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              {course?.title || 'Course Forum'}
            </h1>
          </div>

          {canWrite && (
            <button
              onClick={() => {
                setFormError(null);
                setNewTitle('');
                setNewBody('');
                setIsModalOpen(true);
              }}
              className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm hover:shadow transition"
            >
              <Plus className="w-4 h-4 mr-1.5" />
              New Thread
            </button>
          )}
        </div>
      </div>

      {/* Search box */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="Search threads by title or body..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
        />
      </div>

      {/* Thread list */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
          <p className="text-sm font-medium text-slate-500">Loading threads...</p>
        </div>
      ) : isError ? (
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl flex items-start space-x-3 text-rose-800">
          <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-base">Failed to load forum</h3>
            <p className="text-sm mt-1 text-rose-700">
              {(error as any)?.response?.data?.detail || 'An error occurred.'}
            </p>
          </div>
        </div>
      ) : threads.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-slate-200/80 p-8 shadow-sm">
          <div className="inline-flex p-3 bg-indigo-50 text-indigo-600 rounded-2xl mb-3">
            <MessageSquare className="w-7 h-7" />
          </div>
          <h3 className="font-bold text-slate-900 text-base">No threads yet</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            {debouncedSearch
              ? 'No threads match your search.'
              : 'Be the first to start a discussion in this course forum.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {threads.map((thread) => (
            <Link
              key={thread.id}
              to={`/courses/${courseId}/forum/${thread.id}`}
              className="block bg-white rounded-2xl p-5 border border-slate-200/80 shadow-sm hover:border-indigo-200 hover:shadow transition group"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="flex items-center flex-wrap gap-2">
                    {thread.is_pinned && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-50 text-amber-700 border border-amber-200">
                        <Pin className="w-2.5 h-2.5 mr-0.5" />
                        Pinned
                      </span>
                    )}
                    {thread.is_locked && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200">
                        <Lock className="w-2.5 h-2.5 mr-0.5" />
                        Locked
                      </span>
                    )}
                    <h3 className="text-base font-bold text-slate-900 group-hover:text-indigo-600 transition truncate">
                      {thread.title}
                    </h3>
                  </div>

                  <p className="text-sm text-slate-600 line-clamp-2 leading-relaxed">
                    {thread.body}
                  </p>

                  <div className="flex items-center flex-wrap gap-3 text-xs text-slate-500 pt-1">
                    <span className="font-medium text-slate-700">
                      {thread.author?.full_name || 'Unknown'}
                    </span>
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${roleChipClasses(
                        thread.author?.role || 'student'
                      )}`}
                    >
                      {thread.author?.role || 'student'}
                    </span>
                    <span>{formatRelativeTime(thread.last_activity_at)}</span>
                  </div>
                </div>

                <div className="flex-shrink-0 flex items-center space-x-1.5 text-slate-500">
                  <MessageSquare className="w-4 h-4" />
                  <span className="text-sm font-semibold">{thread.reply_count}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* New Thread Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-lg rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <MessageSquare className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-base">New Thread</h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 rounded-lg p-1 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-2 text-rose-800 text-xs">
                  <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Title *
                </label>
                <input
                  type="text"
                  required
                  maxLength={200}
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="What would you like to discuss?"
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Body *
                </label>
                <textarea
                  required
                  rows={6}
                  maxLength={10000}
                  value={newBody}
                  onChange={(e) => setNewBody(e.target.value)}
                  placeholder="Share your thoughts, questions, or ideas..."
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
                <p className="mt-1 text-xs text-slate-400 text-right">
                  {newBody.length} / 10,000
                </p>
              </div>

              <div className="pt-4 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-100 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 transition"
                >
                  {createMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                      <span>Posting...</span>
                    </>
                  ) : (
                    <span>Create Thread</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
