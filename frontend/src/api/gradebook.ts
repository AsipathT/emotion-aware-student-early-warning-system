import { apiClient } from './client';

export interface GradebookEntry {
  id: string;
  course_id: string;
  student_id: string;
  item_type: string;
  item_id?: string | null;
  title: string;
  score: number;
  max_score: number;
  weight: number;
  recorded_at: string;
  created_at?: string;
  updated_at?: string;
}

export interface GradebookItem {
  key: string;
  title: string;
  item_type: string;
  max_score: number;
  weight: number;
}

export interface StudentGradebookRow {
  student_id: string;
  full_name: string;
  email: string;
  weighted_total: number;
  score_so_far: number;
  entries: GradebookEntry[];
}

export interface CourseGradebookResponse {
  course_id: string;
  items: GradebookItem[];
  students: StudentGradebookRow[];
}

export interface MyGradebookResponse {
  course_id: string;
  student_id: string;
  weighted_total: number;
  score_so_far: number;
  entries: GradebookEntry[];
}

export interface ManualGradePayload {
  student_id: string;
  title: string;
  score: number;
  max_score: number;
  weight?: number;
}

export const gradebookApi = {
  /**
   * Fetches full gradebook grid for instructors and admins.
   */
  getCourseGradebook: async (courseId: string): Promise<CourseGradebookResponse> => {
    const response = await apiClient.get<CourseGradebookResponse>(
      `/courses/${courseId}/gradebook`
    );
    return response.data;
  },

  /**
   * Fetches current student's own grades, weighted total, and progress percentage.
   */
  getMyGradebook: async (courseId: string): Promise<MyGradebookResponse> => {
    const response = await apiClient.get<MyGradebookResponse>(
      `/courses/${courseId}/gradebook/me`
    );
    return response.data;
  },

  /**
   * Adds a manual grade entry (Instructor or Admin only).
   */
  addManualGrade: async (
    courseId: string,
    payload: ManualGradePayload
  ): Promise<GradebookEntry> => {
    const response = await apiClient.post<GradebookEntry>(
      `/courses/${courseId}/gradebook/manual`,
      payload
    );
    return response.data;
  },

  /**
   * Downloads gradebook data as CSV file.
   */
  downloadGradebookCsv: async (courseId: string, courseTitle?: string): Promise<void> => {
    const response = await apiClient.get(`/courses/${courseId}/gradebook/csv`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const safeName = (courseTitle || courseId).replace(/[^a-zA-Z0-9_-]/g, '_');
    a.download = `gradebook_${safeName}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  },
};
