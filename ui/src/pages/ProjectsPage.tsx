import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { projectsApi } from '../api/client';
import type { ProjectSummary } from '../api/client';
import ProjectList from '../components/ProjectList';
import CreateProjectModal from '../components/CreateProjectModal';
import './ProjectsPage.css';

export default function ProjectsPage() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: projects, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await projectsApi.list();
      return response.data;
    },
  });

  const createProjectMutation = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setShowCreateModal(false);
      navigate(`/projects/${response.data.project_id}`);
    },
  });

  const handleProjectClick = (project: ProjectSummary) => {
    navigate(`/projects/${project.project_id}`);
  };

  return (
    <div className="projects-page">
      <div className="projects-header">
        <h2>Projects</h2>
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          + New Project
        </button>
      </div>

      {isLoading && <div className="loading">Loading projects...</div>}
      {error && <div className="error">Error loading projects: {String(error)}</div>}
      {projects && (
        <ProjectList
          projects={projects}
          onProjectClick={handleProjectClick}
          onProjectDelete={() => queryClient.invalidateQueries({ queryKey: ['projects'] })}
        />
      )}

      {showCreateModal && (
        <CreateProjectModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={(data) => createProjectMutation.mutate(data)}
          isSubmitting={createProjectMutation.isPending}
        />
      )}
    </div>
  );
}
