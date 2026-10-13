/**
 * src/pages/SupportPage.tsx
 *
 * Feature 37: Student Support Hub Placeholder (Component 4 Uptake Path).
 * Minimal placeholder page titled "My support" destination for student notifications.
 * Note: Feature 38 (Student Action & Delivery Module) will expand this file into the full interactive support dashboard.
 */

import React from 'react';
import { HeartHandshake, Sparkles, BookOpen, Clock } from 'lucide-react';

export const SupportPage: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="p-2.5 rounded-2xl bg-indigo-50 text-indigo-600">
          <HeartHandshake className="w-7 h-7" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            My Support
          </h1>
          <p className="text-sm text-slate-500">
            Personalized academic guidance, learning resources, and wellbeing consultations.
          </p>
        </div>
      </div>

      {/* Placeholder Welcome Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm text-center">
        <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-4">
          <Sparkles className="w-8 h-8" />
        </div>
        <h2 className="text-lg font-bold text-slate-900 mb-2">
          Your Personalized Support Dashboard
        </h2>
        <p className="text-xs text-slate-600 max-w-md mx-auto leading-relaxed mb-6">
          This page lists support initiatives, advisory sessions, and tailored learning materials approved for your courses.
          Support options offered by university advisors will appear here for you to accept or manage.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg mx-auto text-left">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-3">
            <BookOpen className="w-5 h-5 text-indigo-600 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-bold text-slate-800">Learning Resources</h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Practice quizzes, lecture supplements, and study techniques.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-3">
            <Clock className="w-5 h-5 text-indigo-600 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-bold text-slate-800">Advisory Appointments</h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                One-on-one consultations with academic mentors and counsellors.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-slate-100 text-[11px] text-slate-400">
          Full interactive student delivery module will be active in Feature 38.
        </div>
      </div>
    </div>
  );
};
