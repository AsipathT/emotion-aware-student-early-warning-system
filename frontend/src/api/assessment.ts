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
  content_payload: any;
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
    const res = await apiClient.get(`/courses/${courseId}/assignments`);
    return res.data;
  },
  getQuizzes: async (courseId: string): Promise<Quiz[]> => {
    const res = await apiClient.get(`/courses/${courseId}/quizzes`);
    return res.data;
  },
};
