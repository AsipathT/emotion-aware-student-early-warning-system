import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { enrollmentsApi, EnrollmentResponse } from '../api/enrollments';
import {
  journalApi,
  JournalCurrentStatus,
  JournalEntryResponse,
} from '../api/journal';
import { formatRelativeTime } from '../utils/time';
import {
  BookOpen,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Send,
  Shield,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  X,
  Clock,
  FileText,
  HelpCircle,
} from 'lucide-react';

const WRITING_PROMPTS = [
  "What went well this week?",
  "What felt difficult or confusing?",
  "How are you feeling about this course right now?",
];

function formatUtcWeekRange(startIso: string, endIso: string): string {
  try {
    const start = new Date(startIso);
    const end = new Date(endIso);
    // Subtract 1 second from week_end (which is next Monday 00:00:00 UTC) to represent Sunday
    const sunday = new Date(end.getTime() - 1000);
    const startStr = start.toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    });
    const endStr = sunday.toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    });
    return `${startStr} – ${endStr} (UTC)`;
  } catch {
    return 'Current Week';
  }
}

export const JournalPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null);
  const [body, setBody] = useState<string>('');
  const [expandedEntryIds, setExpandedEntryIds] = useState<Set<string>>(new Set());

  // Toast states
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // 1. Fetch active enrollments
  const {
    data: myEnrollments = [],
    isLoading: enrollmentsLoading,
  } = useQuery<EnrollmentResponse[]>({
    queryKey: ['myEnrollments'],
    queryFn: enrollmentsApi.getMyEnrollments,
  });

  const activeEnrollments = myEnrollments.filter(
    (e) => e.status === 'active'
  );

  // Auto-select first active course
  useEffect(() => {
    if (!selectedCourseId && activeEnrollments.length > 0) {
      setSelectedCourseId(activeEnrollments[0].course_id);
    }
  }, [activeEnrollments, selectedCourseId]);

  // 2. Fetch current week status for selected course
  const {
    data: currentStatus,
    isLoading: statusLoading,
  } = useQuery<JournalCurrentStatus>({
    queryKey: ['journalCurrent', selectedCourseId],
    queryFn: () => journalApi.getCurrentWeekStatus(selectedCourseId!),
    enabled: !!selectedCourseId,
  });

  // 3. Fetch past journal entries for selected course
  const {
    data: entries = [],
    isLoading: entriesLoading,
  } = useQuery<JournalEntryResponse[]>({
    queryKey: ['journalEntries', selectedCourseId],
    queryFn: () =>
      journalApi.getJournalEntries({
        course_id: selectedCourseId!,
        limit: 50,
      }),
    enabled: !!selectedCourseId,
  });

  // 4. Submit journal entry mutation
  const submitMutation = useMutation({
    mutationFn: (text: string) =>
      journalApi.createJournalEntry({
        course_id: selectedCourseId!,
        body: text,
      }),
    onSuccess: () => {
      setSuccessMessage('Your reflection for this week has been recorded.');
      setErrorMessage(null);
      setBody('');
      queryClient.invalidateQueries({ queryKey: ['journalCurrent', selectedCourseId] });
      queryClient.invalidateQueries({ queryKey: ['journalEntries', selectedCourseId] });
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else if (Array.isArray(detail)) {
        setErrorMessage(detail.map((d: any) => d.msg).join(', '));
      } else {
        setErrorMessage('Failed to submit journal entry. Please try again.');
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const stripped = body.trim();
    if (!selectedCourseId || stripped.length < 10 || stripped.length > 5000) return;
    submitMutation.mutate(stripped);
  };

  const toggleExpand = (entryId: string) => {
    setExpandedEntryIds((prev) => {
      const next = new Set(prev);
      if (next.has(entryId)) {
        next.delete(entryId);
      } else {
        next.add(entryId);
      }
      return next;
    });
  };

  const handlePromptClick = (prompt: string) => {
    if (!body) {
      setBody(prompt + '\n\n');
    } else {
      setBody((prev) => prev.trimEnd() + '\n\n' + prompt + '\n\n');
    }
  };

  // Find the submitted entry for the current week if already submitted
  const currentWeekEntry = currentStatus?.submitted
    ? entries.find((e) => e.id === currentStatus.entry_id) || entries[0]
    : null;

  const selectedCourse = activeEnrollments.find(
    (e) => e.course_id === selectedCourseId
  );

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Toast notifications */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between text-emerald-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <span className="font-medium">{successMessage}</span>
          </div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-600 hover:text-emerald-800 p-1 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-between text-rose-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span className="font-medium">{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-rose-600 hover:text-rose-800 p-1 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-2">
            <span className="inline-flex items-center px-2.5 py-0.5 bg-indigo-50 text-indigo-700 rounded-full text-xs font-semibold uppercase tracking-wider">
              <BookOpen className="w-3.5 h-3.5 mr-1.5" />
              Reflective Learning
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Reflective Journal
            </h1>
            <p className="text-sm text-slate-600 max-w-2xl leading-relaxed">
              A private weekly space to pause, reflect on your learning experience, and note down thoughts on your coursework.
            </p>
          </div>
        </div>
      </div>

      {/* Course Selector */}
      {enrollmentsLoading ? (
        <div className="flex items-center justify-center py-12 bg-white rounded-2xl border border-slate-200/80">
          <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      ) : activeEnrollments.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-8 text-center space-y-4">
          <div className="inline-flex p-3 bg-indigo-50 text-indigo-600 rounded-2xl">
            <BookOpen className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">No Active Enrollments</h3>
          <p className="text-sm text-slate-600 max-w-md mx-auto">
            You must be actively enrolled in a course to keep a weekly reflective learning journal.
          </p>
          <Link
            to="/courses"
            className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white font-medium text-sm rounded-xl hover:bg-indigo-700 transition"
          >
            Explore Courses <ArrowRight className="w-4 h-4 ml-1.5" />
          </Link>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Course Tabs */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-2 scrollbar-none">
            {activeEnrollments.map((enr) => {
              const isSelected = enr.course_id === selectedCourseId;
              const courseTitle = enr.course?.title || `Course ${enr.course_id.slice(0, 8)}`;
              return (
                <button
                  key={enr.course_id}
                  onClick={() => setSelectedCourseId(enr.course_id)}
                  className={`px-4 py-2.5 rounded-xl font-medium text-sm whitespace-nowrap transition flex items-center space-x-2 ${
                    isSelected
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <BookOpen className={`w-4 h-4 ${isSelected ? 'text-white' : 'text-slate-400'}`} />
                  <span>{courseTitle}</span>
                </button>
              );
            })}
          </div>

          {/* This Week Reflection Card */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 sm:p-8 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-100 gap-2">
              <div className="flex items-center space-x-2.5">
                <Calendar className="w-5 h-5 text-indigo-600" />
                <h2 className="text-lg font-bold text-slate-900">This Week's Reflection</h2>
              </div>
              {currentStatus && (
                <span className="text-xs font-medium text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
                  {formatUtcWeekRange(currentStatus.week_start, currentStatus.week_end)}
                </span>
              )}
            </div>

            {statusLoading ? (
              <div className="flex items-center justify-center py-10">
                <div className="w-7 h-7 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
              </div>
            ) : currentStatus?.submitted ? (
              /* Already Submitted State */
              <div className="p-6 bg-slate-50/70 border border-slate-200/90 rounded-xl space-y-4">
                <div className="flex items-center space-x-2.5 text-emerald-700 font-semibold text-sm">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                  <span>You have completed your reflection for this calendar week.</span>
                </div>
                {currentWeekEntry && (
                  <div className="space-y-3 pt-2">
                    <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap bg-white p-4 rounded-xl border border-slate-200">
                      {currentWeekEntry.body}
                    </p>
                    <div className="flex items-center space-x-4 text-xs text-slate-400">
                      <span className="flex items-center">
                        <Clock className="w-3.5 h-3.5 mr-1" />
                        Submitted {formatRelativeTime(currentWeekEntry.created_at)}
                      </span>
                      {currentWeekEntry.metadata?.word_count !== undefined && (
                        <span>{currentWeekEntry.metadata.word_count} words</span>
                      )}
                      {currentWeekEntry.metadata?.char_count !== undefined && (
                        <span>{currentWeekEntry.metadata.char_count} characters</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Submission Form */
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Prompt Hints */}
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-slate-500 flex items-center space-x-1">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    <span>Inspiration prompts (click to insert):</span>
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {WRITING_PROMPTS.map((prompt, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handlePromptClick(prompt)}
                        className="px-3 py-1.5 rounded-lg bg-indigo-50/60 hover:bg-indigo-100/70 text-indigo-700 text-xs font-medium border border-indigo-100 transition text-left"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Textarea */}
                <div className="space-y-1.5">
                  <textarea
                    rows={6}
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder="Write your reflection for this week here (10 to 5,000 characters)..."
                    className="w-full p-4 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition leading-relaxed"
                  />
                  <div className="flex items-center justify-between text-xs">
                    <span
                      className={
                        body.trim().length > 0 && body.trim().length < 10
                          ? 'text-rose-600 font-medium'
                          : body.trim().length > 5000
                          ? 'text-rose-600 font-medium'
                          : 'text-slate-400'
                      }
                    >
                      {body.trim().length < 10 && body.trim().length > 0
                        ? `${10 - body.trim().length} more characters needed`
                        : body.trim().length > 5000
                        ? `${body.trim().length - 5000} characters over limit`
                        : 'Minimum 10 characters'}
                    </span>
                    <span
                      className={
                        body.length > 5000
                          ? 'text-rose-600 font-semibold'
                          : 'text-slate-400'
                      }
                    >
                      {body.length} / 5,000
                    </span>
                  </div>
                </div>

                {/* Submit Row */}
                <div className="flex items-center justify-between pt-2">
                  <div className="flex items-center text-xs text-slate-500 space-x-1.5">
                    <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
                    <span>Entries are final and cannot be edited after submission.</span>
                  </div>
                  <button
                    type="submit"
                    disabled={
                      submitMutation.isPending ||
                      body.trim().length < 10 ||
                      body.trim().length > 5000
                    }
                    className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 text-white font-semibold text-sm rounded-xl shadow-sm transition"
                  >
                    {submitMutation.isPending ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4 mr-1.5" />
                        Submit Reflection
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}

            {/* Privacy Assurance Notice */}
            <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200/80 flex items-start space-x-3 text-xs text-slate-600 leading-relaxed">
              <Shield className="w-4 h-4 text-indigo-600 flex-shrink-0 mt-0.5" />
              <span>
                Your journal is private. With your consent, entries are analysed with your identity replaced by a code, only to help staff offer support. They never affect grades.
              </span>
            </div>
          </div>

          {/* Past Entries History */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 sm:p-8 space-y-6">
            <div className="flex items-center space-x-2.5 pb-4 border-b border-slate-100">
              <FileText className="w-5 h-5 text-indigo-600" />
              <h2 className="text-lg font-bold text-slate-900">
                Past Reflections ({entries.length})
              </h2>
            </div>

            {entriesLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-7 h-7 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
              </div>
            ) : entries.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">
                No past journal entries found for {selectedCourse?.course?.title || 'this course'}.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 space-y-4">
                {entries.map((entry) => {
                  const isExpanded = expandedEntryIds.has(entry.id);
                  const isLong = entry.body.length > 200;
                  const displayBody = isExpanded || !isLong
                    ? entry.body
                    : `${entry.body.slice(0, 200)}...`;

                  const weekStartFormatted = new Date(entry.week_start).toLocaleDateString('en-GB', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                    timeZone: 'UTC',
                  });

                  return (
                    <div key={entry.id} className="pt-4 first:pt-0 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-sm text-slate-900">
                            Week of {weekStartFormatted}
                          </span>
                          <span className="text-xs text-slate-400">
                            · {formatRelativeTime(entry.created_at)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-3 text-xs text-slate-400">
                          {entry.metadata?.word_count !== undefined && (
                            <span>{entry.metadata.word_count} words</span>
                          )}
                          {entry.metadata?.char_count !== undefined && (
                            <span>{entry.metadata.char_count} chars</span>
                          )}
                        </div>
                      </div>

                      <div className="bg-slate-50/70 p-4 rounded-xl border border-slate-200/70">
                        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                          {displayBody}
                        </p>
                        {isLong && (
                          <button
                            type="button"
                            onClick={() => toggleExpand(entry.id)}
                            className="mt-2 text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center space-x-1"
                          >
                            <span>{isExpanded ? 'Show less' : 'Read full entry'}</span>
                            {isExpanded ? (
                              <ChevronUp className="w-3.5 h-3.5" />
                            ) : (
                              <ChevronDown className="w-3.5 h-3.5" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Supportive Quiet Footer */}
          <div className="text-center py-4 text-xs text-slate-400">
            If you are struggling, please contact your university counselling service.
          </div>
        </div>
      )}
    </div>
  );
};
