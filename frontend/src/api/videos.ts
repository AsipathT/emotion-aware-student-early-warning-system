import { apiClient } from './client';

export interface VideoViewerRecord {
  student_id: string;
  student_name: string;
  student_email: string;
  total_watch_seconds: number;
  total_watch_minutes: number;
  last_watched_at: string | null;
  completed: boolean;
}

export interface CourseVideo {
  id: string;
  course_id: string;
  title: string;
  description: string;
  filename: string;
  file_size: number;
  content_type: string;
  uploader_name: string;
  created_at: string;
  unique_viewers: number;
  total_watch_seconds: number;
  total_watch_minutes: number;
  my_watch_seconds?: number;
  my_watch_minutes?: number;
  viewers?: VideoViewerRecord[];
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const videosApi = {
  getCourseVideos: async (courseId: string): Promise<CourseVideo[]> => {
    const response = await apiClient.get<CourseVideo[]>(`/courses/${courseId}/videos`);
    return response.data;
  },

  uploadCourseVideo: async (
    courseId: string,
    formData: FormData,
    onUploadProgress?: (progressEvent: any) => void
  ): Promise<CourseVideo> => {
    const response = await apiClient.post<CourseVideo>(`/courses/${courseId}/videos`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress,
    });
    return response.data;
  },

  deleteCourseVideo: async (courseId: string, videoId: string): Promise<void> => {
    await apiClient.delete(`/courses/${courseId}/videos/${videoId}`);
  },

  recordWatchProgress: async (
    videoId: string,
    watchedSeconds: number,
    currentTime: number,
    completed = false
  ): Promise<{ status: string; student_watch_seconds: number; student_watch_minutes: number }> => {
    const response = await apiClient.post(`/videos/${videoId}/watch`, {
      watched_seconds: watchedSeconds,
      current_time: currentTime,
      completed,
    });
    return response.data;
  },

  getVideoStreamUrl: (videoId: string): string => {
    const token = localStorage.getItem('access_token');
    const query = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${API_BASE_URL}/videos/${videoId}/stream${query}`;
  },
};
