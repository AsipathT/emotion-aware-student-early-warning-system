import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Play, Pause, SkipForward, Maximize, Settings } from 'lucide-react';

export const VideoPlayerPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const [isPlaying, setIsPlaying] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);

  const logEvent = (event: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [`[${timestamp}] Clickstream Event: ${event}`, ...prev].slice(0, 5));
    // In a real app, this would send an API request to /api/v1/behaviour/events
  };

  const togglePlay = () => {
    setIsPlaying(!isPlaying);
    logEvent(isPlaying ? 'VIDEO_PAUSE' : 'VIDEO_PLAY');
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900">Lecture Video Player</h1>
        <p className="text-gray-500 mt-1">Feature 9 & 19: Video interaction with clickstream logging (Course: {courseId || 'General'}).</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          {/* Mock Video Player */}
          <div className="bg-black rounded-2xl overflow-hidden shadow-lg aspect-video relative flex flex-col justify-end">
            {/* Center Play Icon */}
            {!isPlaying && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                <button onClick={togglePlay} className="p-4 bg-white/20 rounded-full hover:bg-white/30 backdrop-blur-sm transition">
                  <Play className="w-12 h-12 text-white" fill="white" />
                </button>
              </div>
            )}
            
            {/* Video Controls */}
            <div className="bg-gradient-to-t from-black/80 to-transparent p-4">
              <div className="h-1 bg-gray-600 rounded-full mb-4 overflow-hidden">
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

        {/* Clickstream Logs */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col h-full">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Live Clickstream Logs</h2>
          <div className="flex-1 bg-gray-50 rounded-xl border border-gray-100 p-4 font-mono text-xs text-gray-600 space-y-2 overflow-y-auto">
            {logs.length === 0 ? (
              <p className="text-gray-400 text-center py-8">Interact with the video player to see logs.</p>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="border-b border-gray-200 pb-2 animate-fade-in-down">
                  {log}
                </div>
              ))
            )}
          </div>
          <p className="text-xs text-gray-400 mt-4 text-center">
            These events are aggregated into the weekly background job.
          </p>
        </div>
      </div>
    </div>
  );
};
