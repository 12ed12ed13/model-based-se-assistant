import { useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { versionsApi, diffsApi, recommendationsApi } from '../api/client';
import { jobsApi } from '../api/client';
import DiagramView from './DiagramView';
import DiffView from './DiffView';
import RecommendationsTable from './RecommendationsTable';
import CodeViewer from './CodeViewer';
import './VersionDetails.css';

interface VersionDetailsProps {
  projectId: string;
}

type Tab = 'overview' | 'diagram' | 'ir' | 'analysis' | 'diff' | 'recommendations' | 'code' | 'critique';

export default function VersionDetails({ projectId }: VersionDetailsProps) {
  const { versionId } = useParams<{ versionId: string }>();
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [currentJob, setCurrentJob] = useState<any | null>(null);
  const [isEditingUML, setIsEditingUML] = useState(false);
  const [editedModelText, setEditedModelText] = useState('');
  const [editedModelFormat, setEditedModelFormat] = useState<'plantuml' | 'mermaid' | 'text'>('plantuml');
  const [isStarting, setIsStarting] = useState(false);
  const [showOverlay, setShowOverlay] = useState(false);
  const jobPollRef = useRef<number | null>(null);
  const queryClient = useQueryClient();

  const { data: versionDetail, isLoading, refetch: refetchVersion } = useQuery({
    queryKey: ['version', projectId, versionId],
    queryFn: async () => {
      const response = await versionsApi.get(projectId, versionId!);
      return response.data;
    },
    enabled: !!versionId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const status = data.version?.status;
      return status && status !== 'completed' ? 2000 : false;
    },
  });

  const updateVersionMutation = useMutation({
    mutationFn: async (data: { model_text: string; model_format: 'plantuml' | 'mermaid' | 'text' }) => {
      const response = await versionsApi.update(projectId, versionId!, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['version', projectId, versionId] });
      setIsEditingUML(false);
    },
  });

  const handleEditUML = () => {
    if (versionDetail?.model_text) {
      setEditedModelText(versionDetail.model_text);
      setEditedModelFormat((versionDetail.model_format as 'plantuml' | 'mermaid' | 'text') || 'plantuml');
    }
    setIsEditingUML(true);
  };

  const handleSaveUML = () => {
    updateVersionMutation.mutate({
      model_text: editedModelText,
      model_format: editedModelFormat,
    });
  };

  const handleCancelEdit = () => {
    setIsEditingUML(false);
    setEditedModelText('');
  };

  const handleStartWorkflow = async () => {
    if (!versionId) return;
    setIsStarting(true);
    setShowOverlay(true);
    try {
      const res = await versionsApi.start(projectId, versionId);
      const job = res.data;
      setCurrentJob(job);
      // Poll job status
      const poll = 2000;
      if (jobPollRef.current) window.clearInterval(jobPollRef.current);
      let tick = async () => {
        try {
          const r = await jobsApi.get(projectId, job.job_id);
          const updated = r.data;
          setCurrentJob(updated);
          // Refetch version data on every tick to get intermediate outputs
          refetchVersion?.();
          if (updated.status === 'completed' || updated.status === 'failed') {
            if (jobPollRef.current) window.clearInterval(jobPollRef.current);
            setIsStarting(false);
            // Keep the overlay open so user can see final results
            setShowOverlay(true);
          }
        } catch (e) {
          console.error('Job poll error', e);
          if (jobPollRef.current) window.clearInterval(jobPollRef.current);
        }
      };
      jobPollRef.current = window.setInterval(tick, poll);
      tick();
    } catch (e) {
      console.error('Error starting workflow', e);
      setIsStarting(false);
      setShowOverlay(false);
    }
  };

  const { data: recommendations } = useQuery({
    queryKey: ['recommendations', projectId, versionId],
    queryFn: async () => {
      const response = await recommendationsApi.listByVersion(projectId, versionId!);
      return response.data;
    },
    enabled: !!versionId && activeTab === 'recommendations',
  });

  const { data: diff } = useQuery({
    queryKey: ['diff', projectId, versionDetail?.version.parent_version_id, versionId],
    queryFn: async () => {
      if (!versionDetail?.version.parent_version_id) return null;
      const response = await diffsApi.compare(
        projectId,
        versionDetail.version.parent_version_id,
        versionId!
      );
      return response.data;
    },
    enabled: !!versionId && !!versionDetail?.version.parent_version_id && activeTab === 'diff',
  });

  if (isLoading) {
    return <div className="loading">Loading version details...</div>;
  }

  if (!versionDetail) {
    return <div className="error">Version not found</div>;
  }

  const { version, analysis, code, tests, critique, model_ir } = versionDetail;
  const progress = version.progress || 0;
  const hasModelIR = model_ir && Object.keys(model_ir).length > 0;
  const hasAnalysis = analysis && Object.keys(analysis).length > 0;
  const hasCode = code && Object.keys(code).length > 0;
  const hasTests = tests && Object.keys(tests).length > 0;

  return (
    <div className="version-details">
      <div className="version-header">
        <div>
          <h3>Version {version.version_id.substring(0, 8)}</h3>
          <p className="version-date">
            Created {new Date(version.created_at).toLocaleString()}
            {version.updated_at && version.updated_at !== version.created_at && (
              <span> • Updated {new Date(version.updated_at).toLocaleString()}</span>
            )}
          </p>
        </div>
        <span className={`status-badge status-${version.status}`}>{version.status}</span>
        {version.status !== 'running' && version.status !== 'completed' && (
          <button
            className="btn-primary small"
            onClick={handleStartWorkflow}
            disabled={isStarting || (currentJob && ['queued', 'running'].includes(currentJob.status))}
          >
            {isStarting || (currentJob && ['queued', 'running'].includes(currentJob.status)) ? 'Starting...' : 'Start Workflow'}
          </button>
        )}
        {version.status !== 'running' && versionDetail?.model_text && (
          <button className="btn-secondary small" onClick={handleEditUML}>
            Edit UML
          </button>
        )}
      </div>

      {/* Progress Bar */}
      {(version.status === 'running' || version.status === 'queued') && (
        <div className="progress-container">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }}></div>
          </div>
          <p className="progress-text">{progress}% complete</p>
        </div>
      )}

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`tab ${activeTab === 'diagram' ? 'active' : ''}`}
          onClick={() => setActiveTab('diagram')}
        >
          Diagram
        </button>
        {/* Show IR tab once there is IR available */}
        {hasModelIR && (
          <button
            className={`tab ${activeTab === 'ir' ? 'active' : ''}`}
            onClick={() => setActiveTab('ir')}
          >
            IR
          </button>
        )}
        {/* Show Analysis tab once analysis available */}
        {hasAnalysis && (
          <button
            className={`tab ${activeTab === 'analysis' ? 'active' : ''}`}
            onClick={() => setActiveTab('analysis')}
          >
            Analysis
          </button>
        )}
        {version.parent_version_id && (
          <button
            className={`tab ${activeTab === 'diff' ? 'active' : ''}`}
            onClick={() => setActiveTab('diff')}
          >
            Diff
          </button>
        )}
        <button
          className={`tab ${activeTab === 'recommendations' ? 'active' : ''}`}
          onClick={() => setActiveTab('recommendations')}
        >
          Recommendations
        </button>
        {/* Critique tab (shows issues and refactoring suggestions from CriticAgent) */}
        <button
          className={`tab ${activeTab === 'critique' ? 'active' : ''}`}
          onClick={() => setActiveTab('critique')}
        >
          Critique
        </button>
        <button
          className={`tab ${activeTab === 'code' ? 'active' : ''}`}
          onClick={() => setActiveTab('code')}
        >
          Code & Tests
        </button>
      </div>

      <div className="tab-content">
        {/* Overlay that shows partial outputs and stage progress */}
        {showOverlay && (
          <div className="workflow-overlay">
            <div className="overlay-content">
              <div className="overlay-header">
                <h3>Workflow Running</h3>
                <div className="overlay-actions">
                  <button className="btn-secondary" onClick={() => setShowOverlay(false)} disabled={isStarting || (currentJob && ['queued', 'running'].includes(currentJob.status))}>Close</button>
                </div>
              </div>
              <div className="overlay-body">
                <div className="overlay-stages">
                  <div className={`stage ${hasModelIR ? 'complete' : progress >= 20 ? 'in-progress' : 'pending'}`}>
                    <span className="stage-icon">{hasModelIR ? '✓' : progress >= 20 ? '⟳' : '○'}</span>
                    <span className="stage-label">Parse</span>
                    {hasModelIR && <pre className="stage-preview">{JSON.stringify(model_ir, null, 2)}</pre>}
                  </div>
                  <div className={`stage ${hasAnalysis ? 'complete' : progress >= 40 ? 'in-progress' : 'pending'}`}>
                    <span className="stage-icon">{hasAnalysis ? '✓' : progress >= 40 ? '⟳' : '○'}</span>
                    <span className="stage-label">Analyze</span>
                    {hasAnalysis && (
                      <div className="stage-preview">
                        <p><strong>Summary:</strong> {analysis?.summary || 'No summary available'}</p>
                        <p><strong>Findings:</strong> {(analysis?.findings || []).slice(0, 3).map((f: any) => (<span key={f.issue}>{f.issue}; </span>))}</p>
                      </div>
                    )}
                  </div>
                  <div className={`stage ${hasCode ? 'complete' : progress >= 60 ? 'in-progress' : 'pending'}`}>
                    <span className="stage-icon">{hasCode ? '✓' : progress >= 60 ? '⟳' : '○'}</span>
                    <span className="stage-label">Code</span>
                    {hasCode && <p className="stage-preview">{Object.keys(code || {}).length} files generated</p>}
                  </div>
                  <div className={`stage ${hasTests ? 'complete' : progress >= 80 ? 'in-progress' : 'pending'}`}>
                    <span className="stage-icon">{hasTests ? '✓' : progress >= 80 ? '⟳' : '○'}</span>
                    <span className="stage-label">Tests</span>
                    {hasTests && <p className="stage-preview">{tests?.total_tests || tests?.test_files?.length || 0} tests generated</p>}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        {isEditingUML && (
          <div className="edit-uml-modal">
            <div className="modal-content">
              <h3>Edit UML</h3>
              <div className="form-group">
                <label>Model Format:</label>
                <select value={editedModelFormat} onChange={(e) => setEditedModelFormat(e.target.value as 'plantuml' | 'mermaid' | 'text')}>
                  <option value="plantuml">PlantUML</option>
                  <option value="mermaid">Mermaid</option>
                  <option value="text">Text</option>
                </select>
              </div>
              <div className="form-group">
                <label>Model Text:</label>
                <textarea
                  value={editedModelText}
                  onChange={(e) => setEditedModelText(e.target.value)}
                  rows={20}
                  className="uml-editor"
                />
              </div>
              <div className="modal-actions">
                <button className="btn-primary" onClick={handleSaveUML} disabled={updateVersionMutation.isPending}>
                  {updateVersionMutation.isPending ? 'Saving...' : 'Save'}
                </button>
                <button className="btn-secondary" onClick={handleCancelEdit}>Cancel</button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'overview' && (
          <div className="overview-tab">
            {/* Intermediate Output Status */}
            <div className="workflow-status-section">
              <h4>Workflow Progress</h4>
              <div className="workflow-stages">
                <div className={`stage ${hasModelIR ? 'complete' : progress >= 20 ? 'in-progress' : 'pending'}`}>
                  <span className="stage-icon">{hasModelIR ? '✓' : progress >= 20 ? '⟳' : '○'}</span>
                  <span className="stage-label">Parse Model</span>
                </div>
                <div className={`stage ${hasAnalysis ? 'complete' : progress >= 40 ? 'in-progress' : 'pending'}`}>
                  <span className="stage-icon">{hasAnalysis ? '✓' : progress >= 40 ? '⟳' : '○'}</span>
                  <span className="stage-label">Analyze</span>
                </div>
                <div className={`stage ${hasCode ? 'complete' : progress >= 60 ? 'in-progress' : 'pending'}`}>
                  <span className="stage-icon">{hasCode ? '✓' : progress >= 60 ? '⟳' : '○'}</span>
                  <span className="stage-label">Generate Code</span>
                </div>
                <div className={`stage ${hasTests ? 'complete' : progress >= 80 ? 'in-progress' : 'pending'}`}>
                  <span className="stage-icon">{hasTests ? '✓' : progress >= 80 ? '⟳' : '○'}</span>
                  <span className="stage-label">Generate Tests</span>
                </div>
                <div className={`stage ${progress === 100 ? 'complete' : 'pending'}`}>
                  <span className="stage-icon">{progress === 100 ? '✓' : '○'}</span>
                  <span className="stage-label">Complete</span>
                </div>
              </div>
            </div>

            <div className="metrics-grid">
              <div className="metric-card">
                <h4>Quality Score</h4>
                <p className="metric-value">
                  {version.quality_score !== null
                    ? `${(version.quality_score * 100).toFixed(1)}%`
                    : 'N/A'}
                </p>
              </div>
              <div className="metric-card">
                <h4>Classes</h4>
                <p className="metric-value">{version.metrics?.num_classes || 0}</p>
              </div>
              <div className="metric-card">
                <h4>Findings</h4>
                <p className="metric-value">{analysis?.findings?.length || 0}</p>
              </div>
              <div className="metric-card">
                <h4>Recommendations</h4>
                <p className="metric-value">{analysis?.recommendations?.length || 0}</p>
              </div>
            </div>

            <div className="section">
              <h4>Summary</h4>
              <p>{version.summary}</p>
            </div>

            {analysis?.findings && analysis.findings.length > 0 && (
              <div className="section">
                <h4>Key Findings</h4>
                <ul className="findings-list">
                  {analysis.findings.slice(0, 5).map((finding: any, idx: number) => (
                    <li key={idx} className={`finding-${finding.severity}`}>
                      <strong>{finding.severity}:</strong> {finding.issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {critique && (
              <div className="section">
                <h4>Critique</h4>
                <p>{critique.summary || 'No critique available'}</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'diagram' && (
          <DiagramView projectId={projectId} versionId={versionId!} />
        )}

        {activeTab === 'ir' && hasModelIR && (
          <div className="section">
            <h4>Intermediate Representation (IR)</h4>
            <pre className="json-preview">{JSON.stringify(model_ir, null, 2)}</pre>
          </div>
        )}

        {activeTab === 'analysis' && hasAnalysis && (
          <div className="section">
            <h4>Analysis Report</h4>
            <p><strong>Summary:</strong> {analysis?.summary || 'No summary'}</p>
            <div className="analysis-findings">
              {(analysis?.findings || []).map((f: any, idx: number) => (
                <div key={idx} className={`finding-${f.severity}`}>
                  <strong>{f.severity}:</strong> {f.issue}
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'diff' && diff && (
          <DiffView diff={diff} />
        )}

        {activeTab === 'recommendations' && recommendations && (
          <RecommendationsTable
            recommendations={recommendations}
            projectId={projectId}
          />
        )}

        {activeTab === 'critique' && (
          <div className="section">
            <h4>Critique</h4>
            <p><strong>Summary:</strong> {critique?.summary || 'No critique available'}</p>
            <p><strong>Quality Score:</strong> {critique?.quality_score !== undefined ? `${critique.quality_score}` : 'N/A'}</p>

            {critique?.issues && critique.issues.length > 0 && (
              <div>
                <h5>Issues</h5>
                <ul>
                  {critique.issues.map((issue: any, i: number) => (
                    <li key={i}><strong>{issue.severity || 'info'}:</strong> {issue.description || issue.issue || JSON.stringify(issue)}</li>
                  ))}
                </ul>
              </div>
            )}

            {critique?.refactoring_suggestions && critique.refactoring_suggestions.length > 0 && (
              <div>
                <h5>Refactoring Suggestions</h5>
                <ul>
                  {critique.refactoring_suggestions.map((r: any, idx: number) => (
                    <li key={idx}>
                      <strong>{r.title || 'Suggestion'}:</strong> {r.description || JSON.stringify(r)}
                      {r.affected_entities && r.affected_entities.length > 0 && (
                        <div className="small">Affected: {r.affected_entities.join(', ')}</div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeTab === 'code' && (
          <CodeViewer code={code} tests={tests} />
        )}
      </div>
    </div>
  );
}
