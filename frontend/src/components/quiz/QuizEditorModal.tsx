import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { assessmentApi, Quiz, QuizQuestion } from '../../api/assessment';
import {
  X,
  Plus,
  Trash2,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';

interface QuizEditorModalProps {
  courseId: string;
  isOpen: boolean;
  onClose: () => void;
  quizToEdit?: Quiz | null;
  onSaved?: () => void;
}

export const QuizEditorModal: React.FC<QuizEditorModalProps> = ({
  courseId,
  isOpen,
  onClose,
  quizToEdit,
  onSaved,
}) => {
  const queryClient = useQueryClient();

  // Basic info states
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [timeLimitMinutes, setTimeLimitMinutes] = useState<number | ''>(15);
  const [maxAttempts, setMaxAttempts] = useState<number>(1);
  const [maxScore, setMaxScore] = useState<number>(100);
  const [weight, setWeight] = useState<number>(1.0);
  const [isPublished, setIsPublished] = useState<boolean>(true);

  // Questions array state
  const [questions, setQuestions] = useState<QuizQuestion[]>([
    {
      id: 'q1',
      text: 'What is the primary topic of this module?',
      question_type: 'mcq',
      points: 1.0,
      order: 1,
      options: [
        { id: 'opt1', text: 'Option A (Correct answer)', is_correct: true, order: 1 },
        { id: 'opt2', text: 'Option B', is_correct: false, order: 2 },
      ],
    },
  ]);

  const [formError, setFormError] = useState<string | null>(null);

  // Populate when editing
  useEffect(() => {
    if (quizToEdit) {
      setTitle(quizToEdit.title || '');
      setDescription(quizToEdit.description || '');
      setTimeLimitMinutes(quizToEdit.time_limit_minutes ?? '');
      setMaxAttempts(quizToEdit.max_attempts || 1);
      setMaxScore(quizToEdit.max_score || 100);
      setWeight(quizToEdit.weight || 1.0);
      setIsPublished(quizToEdit.is_published);
      if (quizToEdit.questions && quizToEdit.questions.length > 0) {
        setQuestions(quizToEdit.questions);
      }
    } else {
      setTitle('');
      setDescription('');
      setTimeLimitMinutes(15);
      setMaxAttempts(1);
      setMaxScore(100);
      setWeight(1.0);
      setIsPublished(true);
      setQuestions([
        {
          id: `q_${Date.now()}`,
          text: '',
          question_type: 'mcq',
          points: 1.0,
          order: 1,
          options: [
            { id: `opt_${Date.now()}_1`, text: '', is_correct: true, order: 1 },
            { id: `opt_${Date.now()}_2`, text: '', is_correct: false, order: 2 },
          ],
        },
      ]);
    }
    setFormError(null);
  }, [quizToEdit, isOpen]);

  // Add Question
  const handleAddQuestion = () => {
    const newQId = `q_${Date.now()}`;
    setQuestions((prev) => [
      ...prev,
      {
        id: newQId,
        text: '',
        question_type: 'mcq',
        points: 1.0,
        order: prev.length + 1,
        options: [
          { id: `${newQId}_1`, text: '', is_correct: true, order: 1 },
          { id: `${newQId}_2`, text: '', is_correct: false, order: 2 },
        ],
      },
    ]);
  };

  // Remove Question
  const handleRemoveQuestion = (idx: number) => {
    setQuestions((prev) => prev.filter((_, i) => i !== idx));
  };

  // Update Question text or points
  const handleUpdateQuestion = (idx: number, field: keyof QuizQuestion, value: any) => {
    setQuestions((prev) => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], [field]: value };
      return copy;
    });
  };

  // Add option to question
  const handleAddOption = (qIdx: number) => {
    setQuestions((prev) => {
      const copy = [...prev];
      const q = copy[qIdx];
      const newOptId = `opt_${Date.now()}_${q.options.length + 1}`;
      q.options = [
        ...q.options,
        { id: newOptId, text: '', is_correct: false, order: q.options.length + 1 },
      ];
      return copy;
    });
  };

  // Remove option from question
  const handleRemoveOption = (qIdx: number, optIdx: number) => {
    setQuestions((prev) => {
      const copy = [...prev];
      const q = copy[qIdx];
      if (q.options.length <= 2) {
        return copy; // Keep at least 2 options
      }
      q.options = q.options.filter((_, i) => i !== optIdx);
      return copy;
    });
  };

  // Update option text or set correct
  const handleUpdateOption = (qIdx: number, optIdx: number, text: string) => {
    setQuestions((prev) => {
      const copy = [...prev];
      copy[qIdx].options[optIdx].text = text;
      return copy;
    });
  };

  const handleSetCorrectOption = (qIdx: number, optIdx: number) => {
    setQuestions((prev) => {
      const copy = [...prev];
      copy[qIdx].options = copy[qIdx].options.map((opt, i) => ({
        ...opt,
        is_correct: i === optIdx,
      }));
      return copy;
    });
  };

  // Save Mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!title.trim()) throw new Error('Quiz title is required.');
      if (questions.length === 0) throw new Error('At least one question is required.');

      for (let i = 0; i < questions.length; i++) {
        const q = questions[i];
        if (!q.text.trim()) throw new Error(`Question #${i + 1} text cannot be empty.`);
        if (q.options.length < 2) throw new Error(`Question #${i + 1} must have at least 2 options.`);
        const hasCorrect = q.options.some((o) => o.is_correct);
        if (!hasCorrect) throw new Error(`Question #${i + 1} must have one option designated as correct.`);
      }

      const payload = {
        title: title.trim(),
        description: description.trim() || null,
        time_limit_minutes: timeLimitMinutes ? Number(timeLimitMinutes) : null,
        max_attempts: Number(maxAttempts) || 1,
        max_score: Number(maxScore) || 100,
        weight: Number(weight) || 1.0,
        is_published: isPublished,
        questions,
      };

      if (quizToEdit) {
        return assessmentApi.updateQuiz(courseId, quizToEdit.id, payload);
      } else {
        return assessmentApi.createQuiz(courseId, payload);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['course_quizzes', courseId] });
      queryClient.invalidateQueries({ queryKey: ['course_modules', courseId] });
      if (onSaved) onSaved();
      onClose();
    },
    onError: (err: any) => {
      setFormError(err?.message || err?.response?.data?.detail || 'Failed to save quiz.');
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in overflow-y-auto">
      <div className="bg-white rounded-3xl border border-slate-200 shadow-2xl w-full max-w-3xl my-8 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <HelpCircle className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-base leading-tight">
                {quizToEdit ? 'Edit Assessment Quiz' : 'Create New Assessment Quiz'}
              </h3>
              <p className="text-xs text-slate-400">Configure questions, options, and auto-scoring</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveMutation.mutate();
          }}
          className="p-6 overflow-y-auto flex-1 space-y-6"
        >
          {formError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-rose-800 text-xs font-semibold">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          {/* Basic Info */}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Quiz Title *
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Week 3 Comprehensive Module Checkpoint"
                required
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Description / Instructions
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief guidelines for students before taking the quiz..."
                rows={2}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
              />
            </div>

            {/* Grid settings: time limit, max attempts, max score */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Time Limit (min)
                </label>
                <input
                  type="number"
                  min="0"
                  value={timeLimitMinutes}
                  onChange={(e) => setTimeLimitMinutes(e.target.value === '' ? '' : Number(e.target.value))}
                  placeholder="0 for none"
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Max Attempts
                </label>
                <input
                  type="number"
                  min="1"
                  value={maxAttempts}
                  onChange={(e) => setMaxAttempts(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Max Score
                </label>
                <input
                  type="number"
                  min="1"
                  value={maxScore}
                  onChange={(e) => setMaxScore(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Weight (Gradebook)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={weight}
                  onChange={(e) => setWeight(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                />
              </div>
            </div>

            <div className="flex items-center space-x-2 pt-1">
              <input
                type="checkbox"
                id="isPublishedToggle"
                checked={isPublished}
                onChange={(e) => setIsPublished(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500"
              />
              <label htmlFor="isPublishedToggle" className="text-xs font-semibold text-slate-700">
                Publish immediately (students will be able to see and take this quiz)
              </label>
            </div>
          </div>

          <hr className="border-slate-200" />

          {/* Questions Builder Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-slate-900">Quiz Questions ({questions.length})</h4>
                <p className="text-xs text-slate-500">Design multiple-choice and true/false questions</p>
              </div>

              <button
                type="button"
                onClick={handleAddQuestion}
                className="inline-flex items-center px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs rounded-xl border border-indigo-200 transition"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                Add Question
              </button>
            </div>

            <div className="space-y-4">
              {questions.map((q, qIdx) => (
                <div
                  key={q.id || qIdx}
                  className="bg-slate-50/80 rounded-2xl p-4 border border-slate-200 space-y-3 relative group"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="w-6 h-6 rounded-lg bg-indigo-600 text-white font-extrabold text-xs flex items-center justify-center flex-shrink-0 mt-1">
                      {qIdx + 1}
                    </span>

                    <input
                      type="text"
                      value={q.text}
                      onChange={(e) => handleUpdateQuestion(qIdx, 'text', e.target.value)}
                      placeholder={`Enter question #${qIdx + 1} text...`}
                      required
                      className="flex-1 px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                    />

                    <div className="flex items-center space-x-2 flex-shrink-0">
                      <div className="flex items-center space-x-1">
                        <span className="text-[10px] text-slate-400 font-bold">PTS:</span>
                        <input
                          type="number"
                          min="0.5"
                          step="0.5"
                          value={q.points}
                          onChange={(e) => handleUpdateQuestion(qIdx, 'points', Number(e.target.value))}
                          className="w-14 px-2 py-1 bg-white border border-slate-200 rounded-lg text-xs font-bold text-center"
                        />
                      </div>

                      {questions.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveQuestion(qIdx)}
                          className="p-1.5 text-slate-400 hover:text-rose-600 transition"
                          title="Delete question"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Options */}
                  <div className="pl-9 space-y-2">
                    <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      Select radio button next to the CORRECT answer:
                    </div>

                    {q.options.map((opt, optIdx) => (
                      <div key={opt.id || optIdx} className="flex items-center space-x-2">
                        <input
                          type="radio"
                          name={`correct_${qIdx}`}
                          checked={opt.is_correct}
                          onChange={() => handleSetCorrectOption(qIdx, optIdx)}
                          title="Mark as correct answer"
                          className="w-4 h-4 text-emerald-600 focus:ring-emerald-500 border-slate-300"
                        />

                        <input
                          type="text"
                          value={opt.text}
                          onChange={(e) => handleUpdateOption(qIdx, optIdx, e.target.value)}
                          placeholder={`Option ${String.fromCharCode(65 + optIdx)}`}
                          required
                          className={`flex-1 px-3 py-1.5 rounded-lg border text-xs ${
                            opt.is_correct
                              ? 'bg-emerald-50/60 border-emerald-300 text-emerald-950 font-medium'
                              : 'bg-white border-slate-200 text-slate-700'
                          }`}
                        />

                        {q.options.length > 2 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveOption(qIdx, optIdx)}
                            className="p-1 text-slate-300 hover:text-rose-500"
                            title="Remove option"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    ))}

                    <button
                      type="button"
                      onClick={() => handleAddOption(qIdx)}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center pt-1"
                    >
                      <Plus className="w-3 h-3 mr-1" />
                      Add Another Option
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer Save Buttons */}
          <div className="flex justify-end space-x-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="inline-flex items-center px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow transition disabled:opacity-60"
            >
              {saveMutation.isPending ? 'Saving...' : quizToEdit ? 'Save Changes' : 'Create Quiz'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
