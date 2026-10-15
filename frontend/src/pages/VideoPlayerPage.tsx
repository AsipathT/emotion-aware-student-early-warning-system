import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { videosApi, CourseVideo, VideoViewerRecord } from '../api/videos';
import { coursesApi } from '../api/courses';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../api/client';
import {
  ArrowLeft,
  Upload,
  Play,
  Trash2,
  Users,
  Clock,
  Video as VideoIcon,
  CheckCircle2,
  AlertCircle,
  X,
  FileVideo,
  BarChart3,
  Calendar,
  HardDrive,
  Activity,
  Sparkles,
  Info,
} from 'lucide-react';

export const VideoPlayerPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';
  const isStudent = user?.role === 'student';

  // Video state
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadDesc, setUploadDesc] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Delete modal state
  const [videoToDelete, setVideoToDelete] = useState<CourseVideo | null>(null);

  // Student analytics modal state (for lecturer)
  const [analyticsVideo, setAnalyticsVideo] = useState<CourseVideo | null>(null);

  // Live telemetry feed
  const [telemetryLogs, setTelemetryLogs] = useState<string[]>([]);
  const [lastSynced, setLastSynced] = useState<string | null>(null);

  // Watch heartbeat tracking
  const lastHeartbeatTime = useRef<number>(Date.now());

  // 1. Fetch course details
  const { data: course } = useQuery({
    queryKey: ['course', courseId],
    queryFn: () => coursesApi.getCourseById(courseId!),
    enabled: !!courseId,
  });

  // 2. Fetch course videos with analytics
  const {
    data: videos = [],
    isLoading: isLoadingVideos,
  } = useQuery<CourseVideo[]>({
    queryKey: ['courseVideos', courseId],
    queryFn: () => videosApi.getCourseVideos(courseId!),
    enabled: !!courseId,
  });

  // Set default selected video when loaded
  useEffect(() => {
    if (videos.length > 0 && !selectedVideoId) {
      setSelectedVideoId(videos[0].id);
    }
  }, [videos, selectedVideoId]);

  const activeVideo = videos.find((v) => v.id === selectedVideoId) || videos[0] || null;

  // Telemetry logger helper
  const logTelemetry = async (eventType: string, payload?: any) => {
    const timestamp = new Date().toLocaleTimeString();
    setTelemetryLogs((prev) =>
      [`[${timestamp}] ${eventType}: ${activeVideo?.title || 'Video'}`, ...prev].slice(0, 15)
    );

    if (courseId) {
      try {
        await apiClient.post('/telemetry/events', {
          course_id: courseId,
          week_index: 1,
          event_type: eventType,
          clicks: 1,
          event_payload: {
            video_id: activeVideo?.id,
            timestamp: new Date().toISOString(),
            ...payload,
          },
        });
        setLastSynced(timestamp);
      } catch (err) {
        console.error('Failed to log telemetry:', err);
      }
    }
  };

  // 3. Periodic Watch Time Heartbeat for Students
  useEffect(() => {
    if (!activeVideo || !isStudent) return;

    const interval = setInterval(async () => {
      const vid = videoRef.current;
      if (vid && !vid.paused && !vid.ended) {
        const now = Date.now();
        const deltaSeconds = Math.min((now - lastHeartbeatTime.current) / 1000, 15);
        lastHeartbeatTime.current = now;

        if (deltaSeconds > 0.5) {
          try {
            await videosApi.recordWatchProgress(
              activeVideo.id,
              deltaSeconds,
              vid.currentTime,
              vid.ended
            );
            // Invalidate videos query in background to update analytics
            queryClient.invalidateQueries({ queryKey: ['courseVideos', courseId] });
          } catch (err) {
            console.error('Failed to record watch heartbeat:', err);
          }
        }
      } else {
        lastHeartbeatTime.current = Date.now();
      }
    }, 10000); // Heartbeat every 10 seconds

    return () => clearInterval(interval);
  }, [activeVideo?.id, courseId, isStudent, queryClient]);

  // Video event handlers
  const handlePlay = () => {
    lastHeartbeatTime.current = Date.now();
    logTelemetry('VIDEO_PLAY', { currentTime: videoRef.current?.currentTime });
  };

  const handlePause = () => {
    const vid = videoRef.current;
    if (vid && activeVideo && isStudent) {
      const deltaSeconds = Math.min((Date.now() - lastHeartbeatTime.current) / 1000, 15);
      if (deltaSeconds > 0.5) {
        videosApi.recordWatchProgress(activeVideo.id, deltaSeconds, vid.currentTime, vid.ended);
      }
    }
    logTelemetry('VIDEO_PAUSE', { currentTime: videoRef.current?.currentTime });
  };

  const handleEnded = () => {
    const vid = videoRef.current;
    if (vid && activeVideo && isStudent) {
      videosApi.recordWatchProgress(activeVideo.id, 2, vid.duration || 0, true);
    }
    logTelemetry('VIDEO_ENDED', { completed: true });
  };

  // 4. File Selection & 10MB Limit Validation
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    setFormError(null);
    const file = e.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      return;
    }

    const maxBytes = 10 * 1024 * 1024; // 10 MB limit
    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);

    if (file.size > maxBytes) {
      setFileError(
        `File size exceeds the 10 MB limit! Selected file is ${sizeMB} MB. Please upload a video under 10 MB.`
      );
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    if (!uploadTitle.trim()) {
      // Auto-populate title without extension
      const nameWithoutExt = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
      setUploadTitle(nameWithoutExt);
    }
  };

  // 5. Upload Video Mutation
  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error('Please select a video file.');
      const formData = new FormData();
      formData.append('title', uploadTitle.trim());
      if (uploadDesc.trim()) {
        formData.append('description', uploadDesc.trim());
      }
      formData.append('file', selectedFile);

      return videosApi.uploadCourseVideo(courseId!, formData, (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percent);
        }
      });
    },
    onSuccess: (newVideo) => {
      queryClient.invalidateQueries({ queryKey: ['courseVideos', courseId] });
      setIsUploadOpen(false);
      setUploadTitle('');
      setUploadDesc('');
      setSelectedFile(null);
      setFileError(null);
      setUploadProgress(null);
      setSelectedVideoId(newVideo.id);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message || 'Failed to upload video.';
      setFormError(msg);
      setUploadProgress(null);
    },
  });

  // 6. Delete Video Mutation
  const deleteMutation = useMutation({
    mutationFn: async (videoId: string) => {
      return videosApi.deleteCourseVideo(courseId!, videoId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courseVideos', courseId] });
      setVideoToDelete(null);
      if (selectedVideoId === videoToDelete?.id) {
        setSelectedVideoId(null);
      }
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to delete video.');
    },
  });

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!uploadTitle.trim()) {
      setFormError('Video title is required.');
      return;
    }
    if (!selectedFile) {
      setFormError('Please select a video file to upload.');
      return;
    }

    uploadMutation.mutate();
  };

  // Compute aggregate stats across all course videos for instructors
  const totalUniqueViewers = Array.from(
    new Set(videos.flatMap((v) => (v.viewers || []).map((vw) => vw.student_id)))
  ).length;

  const totalCourseWatchMins = videos.reduce(
    (acc, v) => acc + (v.total_watch_minutes || 0),
    0
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Navigation Breadcrumb */}
      <div>
        <Link
          to={`/courses/${courseId}`}
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-indigo-600 transition group"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5 group-hover:-translate-x-1 transition" />
          Back to Course: {course?.title || 'Details'}
        </Link>
      </div>

      {/* Header Banner */}
      <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-1">
            <VideoIcon className="w-4 h-4" />
            <span>Interactive Lecture Video Hub</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Course Video Lectures
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            {isInstructor
              ? 'Upload, manage, and monitor student watch engagement and duration (Max 10 MB per video).'
              : 'Stream instructor lecture recordings and track your learning progress.'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {lastSynced && (
            <div className="inline-flex items-center px-3 py-1.5 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold rounded-full shadow-xs">
              <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" />
              Telemetry active ({lastSynced})
            </div>
          )}

          {isInstructor && (
            <button
              onClick={() => {
                setUploadTitle('');
                setUploadDesc('');
                setSelectedFile(null);
                setFileError(null);
                setFormError(null);
                setIsUploadOpen(true);
              }}
              className="inline-flex items-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-sm hover:shadow transition"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload Video (Max 10MB)
            </button>
          )}
        </div>
      </div>

      {/* Lecturer Analytics Bar */}
      {isInstructor && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 flex-shrink-0">
              <FileVideo className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                Total Uploaded
              </p>
              <h3 className="text-2xl font-bold text-slate-900 mt-0.5">
                {videos.length} {videos.length === 1 ? 'Video' : 'Videos'}
              </h3>
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 flex-shrink-0">
              <Users className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                Unique Student Viewers
              </p>
              <h3 className="text-2xl font-bold text-slate-900 mt-0.5">
                {totalUniqueViewers} {totalUniqueViewers === 1 ? 'Student' : 'Students'}
              </h3>
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 flex-shrink-0">
              <Clock className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                Total Watch Time
              </p>
              <h3 className="text-2xl font-bold text-slate-900 mt-0.5">
                {totalCourseWatchMins.toFixed(1)} Mins
              </h3>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Layout */}
      {isLoadingVideos ? (
        <div className="py-20 text-center">
          <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-500">Loading lecture video collection...</p>
        </div>
      ) : videos.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center max-w-xl mx-auto shadow-sm">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mx-auto mb-4">
            <FileVideo className="w-8 h-8" />
          </div>
          <h2 className="text-lg font-bold text-slate-900">No Lecture Videos Yet</h2>
          <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">
            {isInstructor
              ? 'You have not uploaded any lecture videos for this course yet. Upload video recordings (up to 10 MB each) to share with your students.'
              : 'Your instructor has not uploaded any lecture videos for this course yet. Please check back later.'}
          </p>
          {isInstructor && (
            <button
              onClick={() => setIsUploadOpen(true)}
              className="mt-6 inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-sm transition"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload First Video
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          {/* Left Column (2 Cols): Active Video Player & Details */}
          <div className="lg:col-span-2 space-y-6">
            {activeVideo && (
              <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                {/* HTML5 Video Player */}
                <div className="bg-black aspect-video relative flex items-center justify-center">
                  <video
                    ref={videoRef}
                    key={activeVideo.id}
                    controls
                    controlsList="nodownload"
                    playsInline
                    className="w-full h-full object-contain"
                    src={videosApi.getVideoStreamUrl(activeVideo.id)}
                    onPlay={handlePlay}
                    onPause={handlePause}
                    onEnded={handleEnded}
                  >
                    Your browser does not support HTML5 video streaming.
                  </video>
                </div>

                {/* Video Info & Analytics Bar */}
                <div className="p-6 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                        {activeVideo.title}
                      </h2>
                      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 mt-1.5">
                        <span className="flex items-center">
                          <Calendar className="w-3.5 h-3.5 mr-1" />
                          {activeVideo.created_at
                            ? new Date(activeVideo.created_at).toLocaleDateString()
                            : 'Recent'}
                        </span>
                        <span>•</span>
                        <span className="flex items-center font-mono">
                          <HardDrive className="w-3.5 h-3.5 mr-1" />
                          {(activeVideo.file_size / (1024 * 1024)).toFixed(2)} MB
                        </span>
                        <span>•</span>
                        <span>By {activeVideo.uploader_name}</span>
                      </div>
                    </div>

                    {/* Instructor Actions */}
                    {isInstructor && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setAnalyticsVideo(activeVideo)}
                          className="inline-flex items-center px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg border border-indigo-200 transition"
                        >
                          <BarChart3 className="w-3.5 h-3.5 mr-1" />
                          Viewer Analytics
                        </button>
                        <button
                          onClick={() => setVideoToDelete(activeVideo)}
                          className="inline-flex items-center px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold rounded-lg border border-rose-200 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5 mr-1" />
                          Delete
                        </button>
                      </div>
                    )}
                  </div>

                  {activeVideo.description && (
                    <p className="text-sm text-slate-600 leading-relaxed bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                      {activeVideo.description}
                    </p>
                  )}

                  {/* Video Engagement Badges */}
                  <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-3 text-xs">
                    <div className="inline-flex items-center px-3 py-1.5 bg-purple-50 text-purple-700 rounded-lg font-medium border border-purple-100">
                      <Users className="w-3.5 h-3.5 mr-1.5 text-purple-600" />
                      <span>{activeVideo.unique_viewers} Students Watched</span>
                    </div>

                    <div className="inline-flex items-center px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-lg font-medium border border-emerald-100">
                      <Clock className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
                      <span>{activeVideo.total_watch_minutes.toFixed(1)} Total Watch Mins</span>
                    </div>

                    {isStudent && (
                      <div className="inline-flex items-center px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg font-medium border border-indigo-100">
                        <Sparkles className="w-3.5 h-3.5 mr-1.5 text-indigo-600" />
                        <span>You watched: {(activeVideo.my_watch_minutes || 0).toFixed(1)} mins</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Clickstream / Telemetry Monitor Box */}
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Activity className="w-4 h-4 text-indigo-600" />
                  <h3 className="text-sm font-bold text-slate-900">Live Video Telemetry Stream</h3>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 bg-slate-100 text-slate-600 rounded">
                  col.activity_events
                </span>
              </div>
              <div className="bg-slate-900 rounded-xl p-3.5 font-mono text-xs text-emerald-400 space-y-1.5 max-h-36 overflow-y-auto shadow-inner">
                {telemetryLogs.length === 0 ? (
                  <p className="text-slate-500 text-center py-4 font-sans text-xs">
                    Play, pause, or scrub video to stream live engagement telemetry to the backend.
                  </p>
                ) : (
                  telemetryLogs.map((log, i) => (
                    <div key={i} className="border-b border-slate-800 pb-1">
                      {log}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right Column (1 Col): Playlist / Library */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900 flex items-center">
                <VideoIcon className="w-4 h-4 text-indigo-600 mr-2" />
                Course Playlist ({videos.length})
              </h3>
              {isInstructor && (
                <button
                  onClick={() => setIsUploadOpen(true)}
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  + Add Video
                </button>
              )}
            </div>

            <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
              {videos.map((vid) => {
                const isActive = vid.id === activeVideo?.id;
                return (
                  <button
                    key={vid.id}
                    onClick={() => setSelectedVideoId(vid.id)}
                    className={`w-full text-left p-3.5 rounded-xl border transition flex flex-col space-y-2 ${
                      isActive
                        ? 'bg-indigo-50/70 border-indigo-300 ring-2 ring-indigo-500/20 shadow-xs'
                        : 'bg-white hover:bg-slate-50 border-slate-200/80'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center space-x-2 truncate">
                        <Play
                          className={`w-4 h-4 flex-shrink-0 ${
                            isActive ? 'text-indigo-600 fill-indigo-600' : 'text-slate-400'
                          }`}
                        />
                        <span
                          className={`font-semibold text-sm truncate ${
                            isActive ? 'text-indigo-950 font-bold' : 'text-slate-800'
                          }`}
                        >
                          {vid.title}
                        </span>
                      </div>
                      {isActive && (
                        <span className="text-[10px] uppercase font-bold bg-indigo-600 text-white px-2 py-0.5 rounded-md flex-shrink-0">
                          Playing
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-100">
                      <span className="flex items-center">
                        <Users className="w-3 h-3 mr-1 text-slate-400" />
                        {vid.unique_viewers} {vid.unique_viewers === 1 ? 'viewer' : 'viewers'}
                      </span>
                      <span className="flex items-center font-mono">
                        <Clock className="w-3 h-3 mr-1 text-slate-400" />
                        {vid.total_watch_minutes.toFixed(1)} mins
                      </span>
                      <span className="text-[11px] text-slate-400">
                        {(vid.file_size / (1024 * 1024)).toFixed(1)}MB
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Upload Video (Lecturer Only) ─────────────────────────────────── */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-lg rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Upload className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-base">Upload Lecture Video</h3>
              </div>
              <button
                onClick={() => setIsUploadOpen(false)}
                className="text-slate-400 hover:text-slate-600 rounded-lg p-1 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-2 text-rose-800 text-xs">
                  <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Notice of 10MB limit */}
              <div className="p-3 bg-indigo-50/60 border border-indigo-100 rounded-xl flex items-start space-x-2 text-indigo-800 text-xs">
                <Info className="w-4 h-4 text-indigo-600 mt-0.5 flex-shrink-0" />
                <span>
                  <strong>Upload Requirement:</strong> Maximum video file size is <strong>10 MB</strong>.
                  Supported formats: MP4, WebM, OGG, MOV.
                </span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Video Title *
                </label>
                <input
                  type="text"
                  required
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="e.g. Lecture 1: Algorithms Introduction"
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Description / Topic Notes
                </label>
                <textarea
                  rows={2}
                  value={uploadDesc}
                  onChange={(e) => setUploadDesc(e.target.value)}
                  placeholder="Key concepts discussed in this recording..."
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>

              {/* File Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Video File (Max 10 MB) *
                </label>
                <input
                  type="file"
                  accept="video/mp4,video/webm,video/ogg,video/quicktime,.mp4,.webm,.ogg,.mov"
                  onChange={handleFileChange}
                  className="block w-full text-xs text-slate-500 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer border border-slate-300 rounded-xl bg-slate-50/50 p-1"
                />

                {fileError && (
                  <div className="mt-2 p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center space-x-1.5">
                    <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                    <span>{fileError}</span>
                  </div>
                )}

                {selectedFile && !fileError && (
                  <div className="mt-2 p-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700 flex items-center justify-between">
                    <div className="flex items-center space-x-1.5 truncate mr-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                      <span className="truncate">{selectedFile.name}</span>
                    </div>
                    <span className="font-mono font-bold flex-shrink-0">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                    </span>
                  </div>
                )}
              </div>

              {/* Upload Progress Bar */}
              {uploadProgress !== null && (
                <div className="space-y-1.5 pt-2">
                  <div className="flex justify-between text-xs font-semibold text-slate-600">
                    <span>Uploading video...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-600 transition-all duration-200 rounded-full"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="pt-4 flex items-center justify-end space-x-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsUploadOpen(false)}
                  disabled={uploadMutation.isPending}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-100 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploadMutation.isPending || !!fileError || !selectedFile}
                  className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-sm disabled:opacity-60 transition"
                >
                  {uploadMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                      <span>Uploading...</span>
                    </>
                  ) : (
                    <span>Upload Video</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: Detailed Student Watch Analytics (Lecturer Only) ────────────── */}
      {analyticsVideo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-2xl rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-slate-900 text-base">
                  Student Viewer Analytics: {analyticsVideo.title}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Detailed watch duration and completion metrics per enrolled student.
                </p>
              </div>
              <button
                onClick={() => setAnalyticsVideo(null)}
                className="text-slate-400 hover:text-slate-600 rounded-lg p-1 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-purple-50/50 border border-purple-100 rounded-xl">
                  <span className="text-xs font-semibold text-purple-700 uppercase">
                    Unique Viewers
                  </span>
                  <p className="text-2xl font-bold text-purple-900 mt-1">
                    {analyticsVideo.unique_viewers} Students
                  </p>
                </div>
                <div className="p-4 bg-emerald-50/50 border border-emerald-100 rounded-xl">
                  <span className="text-xs font-semibold text-emerald-700 uppercase">
                    Total Watch Time
                  </span>
                  <p className="text-2xl font-bold text-emerald-900 mt-1">
                    {analyticsVideo.total_watch_minutes.toFixed(1)} Minutes
                  </p>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Student Watch Breakdown
                </h4>
                {(!analyticsVideo.viewers || analyticsVideo.viewers.length === 0) ? (
                  <p className="text-xs text-slate-400 text-center py-8 bg-slate-50 rounded-xl border border-slate-100">
                    No students have watched this video yet.
                  </p>
                ) : (
                  <div className="border border-slate-200 rounded-xl overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="px-4 py-3">Student</th>
                          <th className="px-4 py-3">Watch Time</th>
                          <th className="px-4 py-3">Last Watched</th>
                          <th className="px-4 py-3">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-slate-700">
                        {analyticsVideo.viewers.map((viewer: VideoViewerRecord, i: number) => (
                          <tr key={i} className="hover:bg-slate-50/60">
                            <td className="px-4 py-3 font-medium text-slate-900">
                              <div>{viewer.student_name}</div>
                              <div className="text-[11px] text-slate-400 font-normal">
                                {viewer.student_email}
                              </div>
                            </td>
                            <td className="px-4 py-3 font-mono font-bold text-indigo-600">
                              {viewer.total_watch_minutes.toFixed(1)} mins ({viewer.total_watch_seconds}s)
                            </td>
                            <td className="px-4 py-3 text-slate-500 font-mono">
                              {viewer.last_watched_at
                                ? new Date(viewer.last_watched_at).toLocaleString()
                                : 'N/A'}
                            </td>
                            <td className="px-4 py-3">
                              {viewer.completed ? (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  Completed
                                </span>
                              ) : (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                                  In Progress
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            <div className="px-6 py-3 border-t border-slate-100 bg-slate-50 flex justify-end">
              <button
                onClick={() => setAnalyticsVideo(null)}
                className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-100 text-slate-700 font-medium text-xs rounded-xl transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Confirm Delete Video (Lecturer Only) ────────────────────────── */}
      {videoToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-md rounded-2xl shadow-xl border border-slate-200 p-6 space-y-4">
            <div className="w-12 h-12 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
              <Trash2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-base">Delete Lecture Video?</h3>
              <p className="text-xs text-slate-500 mt-1">
                Are you sure you want to permanently delete <strong>{videoToDelete.title}</strong>?
                This action will delete the recording and its watch records.
              </p>
            </div>
            <div className="pt-2 flex items-center justify-end space-x-3">
              <button
                onClick={() => setVideoToDelete(null)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(videoToDelete.id)}
                disabled={deleteMutation.isPending}
                className="inline-flex items-center px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs rounded-xl shadow-sm transition"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
