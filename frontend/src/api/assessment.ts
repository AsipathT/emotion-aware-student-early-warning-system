import { apiClient } from './client';

export interface Assignment {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  due_at: string | null;
  max_score: number;
  weight: number;
  is_published: boolean;
  created_at: string;
  updated_at?: string;
}

export interface AssignmentCreatePayload {
  title: string;
  description?: string | null;
  due_at?: string | null;
  max_score: number;
  weight: number;
  is_published: boolean;
}

export interface AssignmentUpdatePayload {
  title?: string;
  description?: string | null;
  due_at?: string | null;
  max_score?: number;
  weight?: number;
  is_published?: boolean;
}

export interface AssignmentSubmission {
  id: string;
  assignment_id: string;
  student_id: string;
  content_text: string | null;
  file_url: string | null;
  submitted_at: string;
  score: number | null;
  feedback: string | null;
  graded_by: string | null;
  graded_at: string | null;
  is_late: boolean;
  delay_days: number;
  created_at: string;
  updated_at: string;
}

export interface AssignmentSubmissionCreatePayload {
  content_text?: string | null;
  file_url?: string | null;
}

export interface AssignmentSubmissionGradePayload {
  score: number;
  feedback?: string | null;
}

export interface Quiz {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  open_at: string | null;
  close_at: string | null;
  time_limit_minutes: number | null;
  max_attempts: number;
  max_score: number;
  weight: number;
  is_published: boolean;
}

export interface Module {
  id: string;
  course_id: string;
  title: string;
  content_payload: Record<string, unknown> | null;
  sequence_order: number;
}

export const contentApi = {
  getModules: async (courseId: string): Promise<Module[]> => {
    const res = await apiClient.get(`/courses/${courseId}/content`);
    return res.data;
  },
};

export const assessmentApi = {
  getAssignments: async (courseId: string): Promise<Assignment[]> => {
    const res = await apiClient.get<Assignment[]>(`/courses/${courseId}/assignments`);
    return res.data;
  },

  getAssignment: async (courseId: string, assignmentId: string): Promise<Assignment> => {
    const res = await apiClient.get<Assignment>(`/courses/${courseId}/assignments/${assignmentId}`);
    return res.data;
  },

  createAssignment: async (courseId: string, payload: AssignmentCreatePayload): Promise<Assignment> => {
    const res = await apiClient.post<Assignment>(`/courses/${courseId}/assignments`, payload);
    return res.data;
  },

  updateAssignment: async (
    courseId: string,
    assignmentId: string,
    payload: AssignmentUpdatePayload
  ): Promise<Assignment> => {
    const res = await apiClient.patch<Assignment>(`/courses/${courseId}/assignments/${assignmentId}`, payload);
    return res.data;
  },

  deleteAssignment: async (courseId: string, assignmentId: string): Promise<void> => {
    await apiClient.delete(`/courses/${courseId}/assignments/${assignmentId}`);
  },

  submitAssignment: async (
    courseId: string,
    assignmentId: string,
    payload: AssignmentSubmissionCreatePayload
  ): Promise<AssignmentSubmission> => {
    const res = await apiClient.post<AssignmentSubmission>(
      `/courses/${courseId}/assignments/${assignmentId}/submit`,
      payload
    );
    return res.data;
  },

  getMySubmission: async (courseId: string, assignmentId: string): Promise<AssignmentSubmission | null> => {
    const res = await apiClient.get<AssignmentSubmission | null>(
      `/courses/${courseId}/assignments/${assignmentId}/my-submission`
    );
    return res.data;
  },

  listSubmissions: async (courseId: string, assignmentId: string): Promise<AssignmentSubmission[]> => {
    const res = await apiClient.get<AssignmentSubmission[]>(
      `/courses/${courseId}/assignments/${assignmentId}/submissions`
    );
    return res.data;
  },

  gradeSubmission: async (
    courseId: string,
    assignmentId: string,
    studentId: string,
    payload: AssignmentSubmissionGradePayload
  ): Promise<AssignmentSubmission> => {
    const res = await apiClient.post<AssignmentSubmission>(
      `/courses/${courseId}/assignments/${assignmentId}/submissions/${studentId}/grade`,
      payload
    );
    return res.data;
  },

  getQuizzes: async (courseId: string): Promise<Quiz[]> => {
    const res = await apiClient.get<Quiz[]>(`/courses/${courseId}/quizzes`);
    return res.data;
  },
};
