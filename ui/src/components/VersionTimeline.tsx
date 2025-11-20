import { useNavigate } from 'react-router-dom';
import type { VersionSummary, WorkflowJobResponse } from '../api/client';
import { formatDistanceToNow } from 'date-fns';
import './VersionTimeline.css';

interface VersionTimelineProps {
  versions: VersionSummary[];
  jobs?: WorkflowJobResponse[] | null;
  projectId: string;
  selectedVersionId?: string;
}

export default function VersionTimeline({ versions, jobs, projectId, selectedVersionId }: VersionTimelineProps) {
  const navigate = useNavigate();

  const items = [
    ...(jobs || []).map((j) => ({
      type: 'job' as const,
      id: j.job_id,
      status: j.status,
      summary: j.message || 'Running analysis...',
      created_at: j.created_at || '',
      version_id: j.version_id || null,
      job: j,
    })),
    ...versions.map((v) => ({
      type: 'version' as const,
      id: v.version_id,
      status: v.status,
      summary: v.summary,
      created_at: v.created_at,
      version_id: v.version_id,
      version: v,
    })),
  ].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  
  if (items.length === 0) {
    return <p className="empty-message">No versions yet</p>;
  }

  return (
    <div className="version-timeline">
      {items.map((item, index) => (
        <div
          key={item.id}
          className={`timeline-item ${item.version_id === selectedVersionId ? 'active' : ''} ${item.type === 'job' ? 'timeline-job' : ''}`}
          onClick={() => {
            if (item.type === 'version') {
              navigate(`/projects/${projectId}/versions/${item.version_id}`);
            }
          }}
        >
          <div className="timeline-marker">
            <div className="timeline-dot" />
            {index < items.length - 1 && <div className="timeline-line" />}
          </div>
          <div className="timeline-content">
            <div className="timeline-header">
              <span className={`status-badge status-${item.status}`}>
                {item.status}{item.type === 'job' ? ' (job)' : ''}
              </span>
              {item.type === 'version' && (item as any).version.quality_score !== null && (
                <span className="quality-score">
                  {(((item as any).version.quality_score ?? 0) * 100).toFixed(0)}%
                </span>
              )}
            </div>
            <p className="version-summary">{item.summary}</p>
            <p className="version-time">
              {formatDistanceToNow(new Date(item.created_at), { addSuffix: true })}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
