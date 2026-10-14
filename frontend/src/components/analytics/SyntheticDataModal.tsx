import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  X,
  Database,
  Sparkles,
  Layers,
  Users,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Cpu,
  Trash2,
} from 'lucide-react';
import {
  analyticsApi,
  CourseOption,
  SyntheticGenerateRequest,
  SyntheticGenerateResponse,
} from '../../api/analytics';

interface SyntheticDataModalProps {
  isOpen: boolean;
  onClose: () => void;
  availableCourses: CourseOption[];
  currentCourseId: string;
}

export const SyntheticDataModal: React.FC<SyntheticDataModalProps> = ({
  isOpen,
  onClose,
  availableCourses,
  currentCourseId,
}) => {
  const queryClient = useQueryClient();
  const [courseId, setCourseId] = useState<string>(currentCourseId || 'CS101');
  const [numStudents, setNumStudents] = useState<number>(10);
  const [numWeeks, setNumWeeks] = useState<number>(6);
  const [cohortProfile, setCohortProfile] = useState<
    'balanced' | 'high_risk_heavy' | 'healthy_cohort' | 'volatile'
  >('balanced');
  const [clearExisting, setClearExisting] = useState<boolean>(true);
  const [result, setResult] = useState<SyntheticGenerateResponse | null>(null);

  const generateMutation = useMutation({
    mutationFn: (payload: SyntheticGenerateRequest) =>
      analyticsApi.generateSyntheticCohort(payload),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ['cohort-risk'] });
    },
  });

  const clearMutation = useMutation({
    mutationFn: (targetCourse: string) => analyticsApi.clearSyntheticData(targetCourse),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cohort-risk'] });
    },
  });

  if (!isOpen) return null;

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault();
    setResult(null);
    generateMutation.mutate({
      course_id: courseId,
      num_students: Number(numStudents),
      num_weeks: Number(numWeeks),
      cohort_profile: cohortProfile,
      clear_existing: clearExisting,
    });
  };

  const handleClear = () => {
    if (window.confirm(`Are you sure you want to purge all synthetic records for course ${courseId}?`)) {
      clearMutation.mutate(courseId);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-2xl w-full flex flex-col overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-5 bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 text-white flex items-center justify-between border-b border-indigo-700/50">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-white/10 rounded-xl backdrop-blur-xs border border-white/15">
              <Sparkles className="w-6 h-6 text-indigo-200" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Synthetic Data Generator
                <span className="text-xs px-2 py-0.5 rounded-full bg-white/20 text-indigo-100 uppercase tracking-wider font-semibold">
                  Feature 41
                </span>
              </h2>
              <p className="text-xs text-indigo-200 mt-0.5">
                Generate multimodal student cohorts, risk assessments & longitudinal telemetry
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-indigo-200 hover:text-white p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleGenerate} className="p-6 space-y-5">
          {/* Target Course */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-indigo-600" />
              Target Course
            </label>
            <select
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
            >
              {availableCourses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.course_code ? `${c.course_code} - ` : ''}{c.title}
                </option>
              ))}
              <option value="CS101">CS101 - Introduction to Computer Systems</option>
              <option value="SE4020">SE4020 - Advanced Software Engineering</option>
            </select>
          </div>

          {/* Grid: Num Students & Num Weeks */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-indigo-600" />
                Cohort Size (Students)
              </label>
              <select
                value={numStudents}
                onChange={(e) => setNumStudents(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
              >
                <option value={5}>5 Students (Fast Demo)</option>
                <option value={10}>10 Students (Standard Cohort)</option>
                <option value={20}>20 Students (Classroom Batch)</option>
                <option value={35}>35 Students (Full Lecture Hall)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-indigo-600" />
                Observation Horizon (Weeks)
              </label>
              <select
                value={numWeeks}
                onChange={(e) => setNumWeeks(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
              >
                <option value={4}>4 Weeks (Early Assessment)</option>
                <option value={6}>6 Weeks (Midterm Trajectory)</option>
                <option value={8}>8 Weeks (Extended Diagnostic)</option>
                <option value={12}>12 Weeks (Full Semester)</option>
              </select>
            </div>
          </div>

          {/* Cohort Profile */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-600" />
              Cohort Risk & Trajectory Profile
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              {[
                {
                  id: 'balanced',
                  title: 'Balanced Cohort',
                  desc: '25% High Risk, 35% Moderate, 40% Consistent',
                },
                {
                  id: 'high_risk_heavy',
                  title: 'High-Risk Heavy',
                  desc: '55% Critical/High risk to test early intervention',
                },
                {
                  id: 'healthy_cohort',
                  title: 'Healthy Cohort',
                  desc: '75% High performers with positive trajectories',
                },
                {
                  id: 'volatile',
                  title: 'Volatile Cohort',
                  desc: 'High rate of erratic and fluctuating engagement',
                },
              ].map((p) => (
                <div
                  key={p.id}
                  onClick={() => setCohortProfile(p.id as any)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all ${
                    cohortProfile === p.id
                      ? 'bg-indigo-50/80 border-indigo-500 shadow-xs'
                      : 'bg-slate-50 border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">{p.title}</span>
                    <input
                      type="radio"
                      name="cohort_profile"
                      checked={cohortProfile === p.id}
                      onChange={() => setCohortProfile(p.id as any)}
                      className="text-indigo-600 focus:ring-indigo-500"
                    />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1 leading-snug">{p.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Clear Existing Checkbox */}
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
            <div className="flex items-center space-x-2.5">
              <input
                type="checkbox"
                id="clearExisting"
                checked={clearExisting}
                onChange={(e) => setClearExisting(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500"
              />
              <label htmlFor="clearExisting" className="text-xs font-medium text-slate-700 cursor-pointer">
                Clear existing synthetic records for this course before generating
              </label>
            </div>
            <button
              type="button"
              onClick={handleClear}
              disabled={clearMutation.isPending}
              className="text-xs text-red-600 hover:text-red-700 font-semibold flex items-center space-x-1 hover:underline"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Purge Now</span>
            </button>
          </div>

          {/* Success Banner */}
          {result && (
            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200 animate-in fade-in space-y-2">
              <div className="flex items-center space-x-2 text-emerald-800 font-bold text-sm">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span>{result.message}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-emerald-200/60 text-xs">
                <div>
                  <span className="text-slate-500">Risk Assessments:</span>{' '}
                  <span className="font-bold text-slate-900">
                    {result.records_generated.risk_assessments}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Trajectories:</span>{' '}
                  <span className="font-bold text-slate-900">
                    {result.records_generated.engagement_trajectories}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Behavior Logs:</span>{' '}
                  <span className="font-bold text-slate-900">
                    {result.records_generated.behavior_weekly}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {generateMutation.isError && (
            <div className="p-4 bg-red-50 rounded-xl border border-red-200 flex items-center space-x-2.5 text-xs text-red-700">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>
                Failed to generate synthetic data: {(generateMutation.error as any)?.message || 'Internal server error'}
              </span>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl transition-colors"
            >
              {result ? 'Done' : 'Cancel'}
            </button>
            <button
              type="submit"
              disabled={generateMutation.isPending}
              className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-xs font-bold rounded-xl shadow-md hover:shadow-lg transition-all flex items-center space-x-2 disabled:opacity-50"
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Synthesizing Cohort...</span>
                </>
              ) : (
                <>
                  <Cpu className="w-4 h-4" />
                  <span>Generate Synthetic Cohort</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
export default SyntheticDataModal;
