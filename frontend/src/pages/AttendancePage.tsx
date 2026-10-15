import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import {
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Clock,
  Plus,
  UserCheck,
  XCircle,
} from 'lucide-react';

interface AttendanceRecord {
  id: string;
  session_id: string;
  course_id: string;
  student_id: string;
  status: 'present' | 'late' | 'absent' | 'excused';
  marked_at: string;
}

interface StudentAttendanceResponse {
  course_id: string;
  student_id: string;
  total_sessions: number;
  attended_sessions: number;
  attendance_rate: number;
  records: AttendanceRecord[];
}

interface AttendanceSession {
  id: string;
  course_id: string;
  title: string;
  session_date: string;
}

export const AttendancePage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';

  // Modal state for creating a session
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sessionTitle, setSessionTitle] = useState('');
  const [sessionDate, setSessionDate] = useState(new Date().toISOString().slice(0, 10));

  // 1. Student view: My attendance
  const { data: myAttendance, isLoading: isLoadingMyAttendance } = useQuery<StudentAttendanceResponse>({
    queryKey: ['myAttendance', courseId],
    queryFn: async () => {
      const res = await apiClient.get<StudentAttendanceResponse>(`/courses/${courseId}/attendance/me`);
      return res.data;
    },
    enabled: !!courseId && !isInstructor,
  });

  // 2. Instructor view: Course sessions
  const { data: sessions = [] } = useQuery<AttendanceSession[]>({
    queryKey: ['attendanceSessions', courseId],
    queryFn: async () => {
      const res = await apiClient.get<AttendanceSession[]>(`/courses/${courseId}/attendance/sessions`);
      return res.data;
    },
    enabled: !!courseId && isInstructor,
  });

  // Create session mutation
  const createSessionMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post(`/courses/${courseId}/attendance/sessions`, {
        title: sessionTitle,
        session_date: new Date(sessionDate).toISOString(),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attendanceSessions', courseId] });
      setIsModalOpen(false);
      setSessionTitle('');
    },
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'present':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" />
            PRESENT
          </span>
        );
      case 'late':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3.5 h-3.5 mr-1 text-amber-600" />
            LATE
          </span>
        );
      case 'excused':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
            EXCUSED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3.5 h-3.5 mr-1 text-rose-600" />
            ABSENT
          </span>
        );
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Navigation Breadcrumb */}
      <div>
        <Link
          to={`/courses/${courseId}`}
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-indigo-600 transition group"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5 group-hover:-translate-x-1 transition" />
          Back to Course Overview
        </Link>
      </div>

      {/* Header Banner */}
      <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-1">
            <UserCheck className="w-4 h-4" />
            <span>Feature 13: Attendance Tracking</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Course Attendance
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Track student session participation and longitudinal attendance rates.
          </p>
        </div>

        {isInstructor ? (
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-sm transition"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Session
          </button>
        ) : myAttendance && (
          <div className="flex items-center gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
            <div>
              <div className="text-xs text-slate-500 font-medium">Overall Attendance</div>
              <div className="text-2xl font-black text-indigo-600">
                {myAttendance.attendance_rate}%
              </div>
            </div>
            <div className="text-xs text-slate-400 border-l border-slate-200 pl-4">
              <div>{myAttendance.attended_sessions} / {myAttendance.total_sessions} Sessions Attended</div>
            </div>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
        {isInstructor ? (
          /* Instructor Session List */
          <div>
            <div className="p-6 border-b border-slate-100 flex justify-between items-center">
              <h2 className="text-lg font-bold text-slate-900 flex items-center">
                <Calendar className="w-5 h-5 text-indigo-600 mr-2" />
                Scheduled Attendance Sessions ({sessions.length})
              </h2>
            </div>
            {sessions.length === 0 ? (
              <div className="p-12 text-center text-slate-400 text-sm">
                No attendance sessions created yet. Click "New Session" above to start taking attendance.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {sessions.map((s) => (
                  <div key={s.id} className="p-5 flex justify-between items-center hover:bg-slate-50/50 transition">
                    <div>
                      <h3 className="font-semibold text-slate-900 text-sm">{s.title}</h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {new Date(s.session_date).toLocaleDateString()} at{' '}
                        {new Date(s.session_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                    <span className="text-xs font-semibold px-3 py-1 bg-indigo-50 text-indigo-700 rounded-lg">
                      Session Recorded
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Student Records List */
          <div>
            <div className="p-6 border-b border-slate-100">
              <h2 className="text-lg font-bold text-slate-900 flex items-center">
                <UserCheck className="w-5 h-5 text-indigo-600 mr-2" />
                My Session Attendance History
              </h2>
            </div>
            {isLoadingMyAttendance ? (
              <div className="p-12 text-center text-slate-400">Loading attendance history...</div>
            ) : !myAttendance || myAttendance.records.length === 0 ? (
              <div className="p-12 text-center text-slate-400 text-sm">
                No attendance records logged yet for your profile in this course.
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
                    <th className="p-4 border-b border-slate-200">Session ID</th>
                    <th className="p-4 border-b border-slate-200">Recorded Date</th>
                    <th className="p-4 border-b border-slate-200 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {myAttendance.records.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/50 transition">
                      <td className="p-4 font-mono text-xs text-slate-600">{r.session_id}</td>
                      <td className="p-4 text-slate-600">
                        {new Date(r.marked_at).toLocaleDateString()}
                      </td>
                      <td className="p-4 text-right">{getStatusBadge(r.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Create Session Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Schedule Attendance Session</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Session Title</label>
                <input
                  type="text"
                  value={sessionTitle}
                  onChange={(e) => setSessionTitle(e.target.value)}
                  placeholder="e.g. Week 3 Lecture: Machine Learning Foundations"
                  className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Date</label>
                <input
                  type="date"
                  value={sessionDate}
                  onChange={(e) => setSessionDate(e.target.value)}
                  className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-3">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 border border-slate-200 text-slate-600 rounded-xl text-sm font-semibold hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={() => createSessionMutation.mutate()}
                disabled={!sessionTitle.trim() || createSessionMutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
              >
                {createSessionMutation.isPending ? 'Saving...' : 'Create Session'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
