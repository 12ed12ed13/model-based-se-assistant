import type { ProjectSummary } from '../api/client';
import { formatDistanceToNow } from 'date-fns';
import './ProjectList.css';
import { projectsApi } from '../api/client';

interface ProjectListProps {
  projects: ProjectSummary[];
  onProjectClick: (project: ProjectSummary) => void;
  onProjectDelete?: (project: ProjectSummary) => void;
}

export default function ProjectList({ projects, onProjectClick, onProjectDelete }: ProjectListProps) {
  const handleDelete = async (e: React.MouseEvent, project: ProjectSummary) => {
    e.stopPropagation();
    try {
      await projectsApi.delete(project.project_id);
      if (onProjectDelete) {
        onProjectDelete(project);
      }
    } catch (err) {
      console.error('Failed to delete project', err);
    }
  };

  if (projects.length === 0) {
    return (
      <div className="empty-state">
        <p>No projects yet. Create your first project to get started.</p>
      </div>
    );
  }

  return (
    <div className="project-list">
      {projects.map((project) => (
        <div
          key={project.project_id}
          className="card project-card"
          onClick={() => onProjectClick(project)}
        >
          <div className="project-card-header">
            <h3>{project.name || project.project_id}</h3>
            {project.latest_status && (
              <span className={`status-badge status-${project.latest_status}`}>
                {project.latest_status}
              </span>
            )}
          </div>
          <p className="project-description">{project.description || 'No description'}</p>
          <div className="project-card-footer">
            <div className="project-meta">
              {project.latest_quality_score !== null && (
                <div className="meta-item">
                  <span className="label">Quality</span>
                  <span className="value quality-score">
                    {(project.latest_quality_score * 100).toFixed(0)}%
                  </span>
                </div>
              )}
              <div className="meta-item">
                <span className="label">Versions</span>
                <span className="value">
                  {project.latest_version_id ? 'Active' : 'None'}
                </span>
              </div>
            </div>
            <div className="card-actions">
              <span className="updated-at">
                {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
              </span>
              <button
                className="btn-icon delete-btn"
                onClick={(e) => handleDelete(e, project)}
                title="Delete project"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 6h18"></path>
                  <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                  <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}


