import React from 'react';
import { useParams } from 'react-router-dom';

export const AttendancePage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();

  // Mock attendance data
  const sessions = [
    { id: '1', date: '2026-10-01', title: 'Lecture 1: Introduction', status: 'present' },
    { id: '2', date: '2026-10-03', title: 'Lecture 2: Supervised Learning', status: 'present' },
    { id: '3', date: '2026-10-08', title: 'Lecture 3: Deep Neural Networks', status: 'absent' },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Attendance Tracker</h1>
          <p className="text-gray-500 mt-1">Feature 13: Attendance sessions and records (Course: {courseId || 'General'}).</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 text-gray-500 text-sm">
              <th className="p-4 font-medium border-b border-gray-200">Date</th>
              <th className="p-4 font-medium border-b border-gray-200">Session</th>
              <th className="p-4 font-medium border-b border-gray-200 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sessions.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50 transition-colors">
                <td className="p-4 text-sm text-gray-600 font-mono">{s.date}</td>
                <td className="p-4 text-sm text-gray-900 font-medium">{s.title}</td>
                <td className="p-4 text-sm text-right">
                  <span
                    className={`inline-flex px-2.5 py-1 rounded-full text-xs font-semibold ${
                      s.status === 'present'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-rose-50 text-rose-700 border border-rose-200'
                    }`}
                  >
                    {s.status.toUpperCase()}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
