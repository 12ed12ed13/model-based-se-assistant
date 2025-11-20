import { useMemo, useState } from 'react';
import { useParams, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { projectsApi, versionsApi, jobsApi, recommendationsApi, type RecommendationSummary, type VersionDetail } from '../api/client';
import VersionTimeline from '../components/VersionTimeline';
import VersionDetails from '../components/VersionDetails';
import CreateVersionModal from '../components/CreateVersionModal';
import VersionResultModal from '../components/VersionResultModal';
import './ProjectDetailPage.css';

export default function ProjectDetailPage() {
  const { projectId, versionId: routeVersionId } = useParams<{ projectId: string; versionId: string }>();
  const navigate = useNavigate();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showResultModal, setShowResultModal] = useState(false);
  const [resultVersionId, setResultVersionId] = useState<string | null>(null);
  const [baselineDetail, setBaselineDetail] = useState<VersionDetail | null>(null);
  const [baselineRecommendations, setBaselineRecommendations] = useState<RecommendationSummary[]>([]);

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: async () => {
      const response = await projectsApi.get(projectId!);
      return response.data;
    },
    enabled: !!projectId,
  });

  const { data: rawVersions, refetch: refetchVersions } = useQuery({
    queryKey: ['versions', projectId],
    queryFn: async () => {
      const response = await versionsApi.list(projectId!);
      return response.data;
    },
    enabled: !!projectId,
  });

  const versions = useMemo(() => {
    if (!rawVersions) return [];
    return [...rawVersions].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [rawVersions]);

  const { data: jobsList } = useQuery({
    queryKey: ['jobs', projectId],
    queryFn: async () => {
      const response = await jobsApi.list(projectId!);
      return response.data;
    },
    enabled: !!projectId,
  });

  const currentVersion = versions?.find(v => v.version_id === routeVersionId);

  // Fetch full details for current version to get model text for editing
  const { data: currentVersionDetail } = useQuery({
    queryKey: ['version', projectId, currentVersion?.version_id],
    queryFn: async () => {
      if (!currentVersion?.version_id) return null;
      const response = await versionsApi.get(projectId!, currentVersion.version_id);
      return response.data;
    },
    enabled: !!currentVersion?.version_id,
  });

  // Fetch recommendations for current version to show in create modal
  const { data: currentRecommendations } = useQuery({
    queryKey: ['recommendations', projectId, currentVersion?.version_id],
    queryFn: async () => {
      if (!currentVersion?.version_id) return [];
      const response = await recommendationsApi.listByVersion(projectId!, currentVersion.version_id);
      return response.data;
    },
    enabled: !!currentVersion?.version_id,
  });

  const handleCreateVersion = async (data: any) => {
    try {
      if (currentVersionDetail) {
        setBaselineDetail(currentVersionDetail);
      } else {
        setBaselineDetail(null);
      }
      setBaselineRecommendations(currentRecommendations || []);
      const res = await versionsApi.create(projectId!, data);
      const newVersion = res.data;
      setShowCreateModal(false);
      
      // Set result modal state
      setResultVersionId(newVersion.version_id);
      
      // Start the workflow
      try {
        await versionsApi.start(projectId!, newVersion.version_id);
      } catch (startErr) {
        console.error('Error starting workflow for new version:', startErr);
      }
      
      // Immediately update versions list and show result modal
      await refetchVersions();
      setShowResultModal(true);
      
      // Navigate to the new version so user can see "Start Workflow" button and edit UML
      navigate(`versions/${newVersion.version_id}`);
    } catch (error) {
      console.error('Error creating version:', error);
    }
  };

  return (
    <div className="project-detail-page">
      <div className="project-header">
        <button className="btn-back" onClick={() => navigate('/projects')}>
          ← Back to Projects
        </button>
        <div className="project-info">
          <h2>{project?.name || project?.project_id}</h2>
          <p className="project-description">{project?.description}</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          + New Version
        </button>
      </div>

      <div className="project-content">
        <aside className="version-sidebar">
          <h3>Version Timeline</h3>
          {versions && (
            <VersionTimeline
              versions={versions}
              jobs={jobsList}
              projectId={projectId!}
              selectedVersionId={routeVersionId}
            />
          )}
        </aside>

        <main className="version-main">
          <Routes>
            <Route index element={
              versions && versions.length > 0 ? (
                <Navigate to={`versions/${versions[0].version_id}`} replace />
              ) : (
                <div className="empty-state">
                  <p>No versions yet. Create your first version to get started.</p>
                </div>
              )
            } />
            <Route path="versions/:versionId" element={
              <VersionDetails projectId={projectId!} />
            } />
          </Routes>
        </main>
      </div>

      {showCreateModal && (
        <CreateVersionModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={handleCreateVersion}
          initialModelText={currentVersionDetail?.model_text || ''}
          initialModelFormat={currentVersionDetail?.model_format as any}
          recommendations={currentRecommendations || []}
        />
      )}

      {showResultModal && resultVersionId && (
        <VersionResultModal
          projectId={projectId!}
          versionId={resultVersionId}
          baselineAnalysis={baselineDetail?.analysis || null}
          baselineVersion={baselineDetail?.version || null}
          previousRecommendations={baselineRecommendations}
          onClose={() => {
            setShowResultModal(false);
            setResultVersionId(null);
          }}
          onViewVersion={() => {
            if (resultVersionId) {
              navigate(`versions/${resultVersionId}`);
            }
            setShowResultModal(false);
          }}
        />
      )}
    </div>
  );
}
