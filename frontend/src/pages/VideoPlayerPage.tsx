import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Play, Pause, SkipForward, Maximize, Settings, ArrowLeft, Activity, CheckCircle2 } from 'lucide-react';
import { apiClient } from '../api/client';

export const VideoPlayerPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const [isPlaying, setIsPlaying] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [lastSynced, setLastSynced] = useState<string | null>(null);

  const logEvent = async (event: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [`[${timestamp}] Clickstream Event: ${event}`, ...prev].slice(0, 10));

    // Send real telemetry event to backend
    if (courseId) {
      try {
        await apiClient.post('/telemetry/events', {
          course_id: courseId,
          week_index: 1,
          event_type: event,
          clicks: 1,
          event_payload: {
            timestamp: new Date().toISOString(),
            player_state: isPlaying ? 'playing' : 'paused',
          },
        });
        setLastSynced(timestamp);
      } catch (err) {
        console.error('Failed to log telemetry event:', err);
      }
    }
  };

  const togglePlay = () => {
    const nextState = !isPlaying;
    setIsPlaying(nextState);
    logEvent(nextState ? 'VIDEO_PLAY' : 'VIDEO_PAUSE');
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Navigation Breadcrumb */}
      <div>
        <Link
          to={`/courses/${courseId}`}
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-indigo-600 transition group"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5 group-hover:-translate-x-1 transition" />
          Back to Course Details
        </Link>
      </div>

      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Lecture Video Player</h1>
          <p className="text-gray-500 mt-1">Feature 9 & 19: Real-time telemetry tracking & clickstream logging (Course: {courseId || 'General'}).</p>
        </div>
        {lastSynced && (
          <div className="inline-flex items-center px-3 py-1.5 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold rounded-full">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" />
            Telemetry Synced at {lastSynced}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          {/* Mock Video Player */}
          <div className="bg-black rounded-2xl overflow-hidden shadow-lg aspect-video relative flex flex-col justify-end">
            {/* Center Play Icon */}
            {!isPlaying && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                <button
                  onClick={togglePlay}
                  className="p-5 bg-white/20 rounded-full hover:bg-white/30 backdrop-blur-sm transition transform hover:scale-110"
                >
                  <Play className="w-12 h-12 text-white" fill="white" />
                </button>
              </div>
            )}
            
            {/* Video Controls */}
            <div className="bg-gradient-to-t from-black/80 to-transparent p-5">
              <div className="h-1.5 bg-gray-600 rounded-full mb-4 overflow-hidden cursor-pointer" onClick={() => logEvent('VIDEO_SEEK')}>
                <div className="h-full bg-indigo-500 w-1/3"></div>
              </div>
              <div className="flex items-center justify-between text-white">
                <div className="flex items-center space-x-4">
                  <button onClick={togglePlay} className="hover:text-indigo-400 transition">
                    {isPlaying ? <Pause className="w-6 h-6" fill="currentColor" /> : <Play className="w-6 h-6" fill="currentColor" />}
                  </button>
                  <button onClick={() => logEvent('VIDEO_SEEK_FORWARD')} className="hover:text-indigo-400 transition">
                    <SkipForward className="w-5 h-5" />
                  </button>
                  <span className="text-sm font-medium">12:34 / 45:00</span>
                </div>
                <div className="flex items-center space-x-4">
                  <button onClick={() => logEvent('VIDEO_SETTINGS_CLICKED')} className="hover:text-indigo-400 transition">
                    <Settings className="w-5 h-5" />
                  </button>
                  <button onClick={() => logEvent('VIDEO_FULLSCREEN')} className="hover:text-indigo-400 transition">
                    <Maximize className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Live Clickstream Logs */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col h-full">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-900 flex items-center">
              <Activity className="w-5 h-5 text-indigo-600 mr-2" />
              Live Clickstream Logs
            </h2>
            <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-700 font-bold rounded-full">
              col.activity_events
            </span>
          </div>
          <div className="flex-1 bg-slate-900 rounded-xl p-4 font-mono text-xs text-emerald-400 space-y-2 overflow-y-auto max-h-80 shadow-inner">
            {logs.length === 0 ? (
              <p className="text-slate-500 text-center py-10 font-sans">
                Click controls in the player to trigger live clickstream telemetry events.
              </p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="border-b border-slate-800 pb-1.5 font-mono">
                  {log}
                </div>
              ))
            )}
          </div>
          <p className="text-xs text-gray-400 mt-4 text-center">
            Events are persisted to MongoDB Atlas and processed by Feature 20 Weekly Aggregation.
          </p>
        </div>
      </div>
    </div>
  );
};
