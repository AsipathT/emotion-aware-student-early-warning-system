import React, { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { telemetryApi } from '../../api/telemetry';

export const ClickstreamTracker: React.FC = () => {
  const location = useLocation();
  const { user } = useAuth();
  const lastPathRef = useRef<string>('');

  useEffect(() => {
    // Only track if user is authenticated and location actually changed
    if (!user || location.pathname === lastPathRef.current) return;
    lastPathRef.current = location.pathname;

    // Extract courseId if navigating within a course route
    const courseMatch = location.pathname.match(/\/courses\/([^/]+)/);
    const courseId = courseMatch ? courseMatch[1] : 'general';

    // Dispatch background telemetry event silently
    telemetryApi
      .logEvent({
        course_id: courseId,
        week_index: 1,
        event_type: 'page_view',
        event_payload: {
          path: location.pathname,
          search: location.search,
          timestamp: new Date().toISOString(),
          title: document.title,
        },
        clicks: 1,
      })
      .catch(() => {
        // Silent catch: telemetry should never disrupt user browsing
      });
  }, [location.pathname, location.search, user]);

  return null;
};
