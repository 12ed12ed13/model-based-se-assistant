import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  versionsApi,
  recommendationsApi,
  type RecommendationSummary,
  type VersionSummary,
} from '../api/client';
import './VersionResultModal.css';

interface VersionResultModalProps {
  projectId: string;
  versionId: string;
  baselineAnalysis: Record<string, any> | null;
  baselineVersion: VersionSummary | null;
  previousRecommendations: RecommendationSummary[];
  onClose: () => void;
  onViewVersion: () => void;
}

export default function VersionResultModal({
  projectId,
  versionId,
  baselineAnalysis,
  baselineVersion,
  previousRecommendations,
  onClose,
  onViewVersion,
}: VersionResultModalProps) {
  const { data: detail } = useQuery({
    queryKey: ['version-result-modal', projectId, versionId],
    queryFn: async () => {
      const response = await versionsApi.get(projectId, versionId);
      return response.data;
    },
    enabled: !!projectId && !!versionId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      return data.version.status !== 'completed' ? 2000 : false;
    },
  });

  const { data: newRecommendations } = useQuery({
    queryKey: ['recommendations', projectId, versionId, 'result-modal'],
    queryFn: async () => {
      const response = await recommendationsApi.listByVersion(projectId, versionId);
      return response.data;
    },
    enabled: !!projectId && !!versionId,
  });

  const versionStatus = detail?.version.status ?? 'queued';
  const progress = detail?.version.progress ?? 0;
  const isCompleted = versionStatus === 'completed';

  const previousQuality = baselineVersion?.quality_score ?? null;
  const currentQuality = detail?.version.quality_score ?? null;
  const qualityDelta = previousQuality !== null && currentQuality !== null
    ? currentQuality - previousQuality
    : null;

  const previousFindings = baselineAnalysis?.findings?.length ?? 0;
  const currentFindings = detail?.analysis?.findings?.length ?? 0;
  const findingsDelta = previousFindings - currentFindings;

  const previousMetrics = baselineAnalysis?.quality_metrics ?? {};
  const currentMetrics = detail?.analysis?.quality_metrics ?? {};
  const metricKeys = useMemo(() => {
    return Array.from(new Set([
      ...Object.keys(previousMetrics || {}),
      ...Object.keys(currentMetrics || {}),
    ]));
  }, [previousMetrics, currentMetrics]);

  const newFindingTexts = useMemo(() => {
    return new Set((detail?.analysis?.findings || []).map((f: any) => (f.issue || f.title || '').toLowerCase()));
  }, [detail?.analysis?.findings]);

  const recommendationStatuses = previousRecommendations.map((rec) => {
    const key = (rec.title || '').toLowerCase();
    if (!key) {
      return { ...rec, resolved: false };
    }
    const unresolved = Array.from(newFindingTexts).some((finding) => typeof finding === 'string' && finding.includes(key));
    return { ...rec, resolved: !unresolved };
  });

  const combinedRecommendations = newRecommendations && newRecommendations.length > 0
    ? newRecommendations
    : previousRecommendations;

  const formatQuality = (value: number | null) => {
    if (value === null || value === undefined) return 'N/A';
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatDelta = (value: number | null, formatter: (val: number) => string) => {
    if (value === null || value === undefined) return '—';
    if (value === 0) return '0';
    const prefix = value > 0 ? '+' : '';
    return `${prefix}${formatter(value)}`;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content comparison-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>Updated Version Overview</h2>
            <p className="modal-subtitle">Tracking improvements against the previous architecture</p>
          </div>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="comparison-body">
          {!detail && (
            <div className="loading-state">
              <p>Fetching the latest workflow status...</p>
            </div>
          )}

          {detail && (
            <>
              <div className={`status-banner status-${versionStatus}`}>
                <div>
                  <p><strong>Status:</strong> {versionStatus.toUpperCase()}</p>
                  {!isCompleted && <p className="status-hint">We will refresh this view automatically as each stage completes.</p>}
                </div>
                <div className="banner-progress">
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${progress}%` }} />
                  </div>
                  <span>{progress}%</span>
                </div>
              </div>

              <div className="comparison-grid">
                <div className="metric-card">
                  <h4>Quality Score</h4>
                  <p className="metric-value">{formatQuality(currentQuality)}</p>
                  <p className={`metric-delta ${qualityDelta !== null && qualityDelta >= 0 ? 'positive' : 'negative'}`}>
                    {qualityDelta !== null ? formatDelta(qualityDelta * 100, (val) => `${val.toFixed(1)}%`) : '—'} compared to {(previousQuality !== null) ? formatQuality(previousQuality) : 'previous version'}
                  </p>
                </div>
                <div className="metric-card">
                  <h4>Open Findings</h4>
                  <p className="metric-value">{currentFindings}</p>
                  <p className={`metric-delta ${findingsDelta >= 0 ? 'positive' : 'negative'}`}>
                    {findingsDelta !== 0 ? `${findingsDelta > 0 ? '-' : '+'}${Math.abs(findingsDelta)} vs previous` : 'No change yet'}
                  </p>
                </div>
                <div className="metric-card">
                  <h4>Recommendations Addressed</h4>
                  <p className="metric-value">
                    {recommendationStatuses.filter((r) => r.resolved).length}/{recommendationStatuses.length || '0'}
                  </p>
                  <p className="metric-delta">Based on prior recommendations</p>
                </div>
              </div>

              {metricKeys.length > 0 && (
                <div className="metrics-table">
                  <h4>Quality Metric Comparison</h4>
                  <table>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Previous</th>
                        <th>Updated</th>
                        <th>Δ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metricKeys.map((key) => {
                        const prevValue = previousMetrics?.[key] ?? null;
                        const newValue = currentMetrics?.[key] ?? null;
                        const delta = (typeof prevValue === 'number' && typeof newValue === 'number')
                          ? newValue - prevValue
                          : null;
                        return (
                          <tr key={key}>
                            <td>{key}</td>
                            <td>{prevValue ?? '—'}</td>
                            <td>{newValue ?? '—'}</td>
                            <td className={delta !== null ? (delta >= 0 ? 'delta-positive' : 'delta-negative') : ''}>
                              {delta !== null ? `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}` : '—'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="analysis-summary">
                <div>
                  <h4>Updated Summary</h4>
                  <p>{detail.analysis?.summary || 'Summary is not available yet.'}</p>
                </div>
                <div>
                  <h4>Previous Summary</h4>
                  <p>{baselineAnalysis?.summary || 'No baseline summary was available.'}</p>
                </div>
              </div>

              {recommendationStatuses.length > 0 && (
                <div className="recommendation-statuses">
                  <h4>Recommendation Follow-up</h4>
                  <div className="recommendation-list">
                    {recommendationStatuses.map((rec) => (
                      <div key={rec.rec_id} className={`recommendation-row ${rec.resolved ? 'resolved' : 'pending'}`}>
                        <div>
                          <p className="rec-title">{rec.title}</p>
                          <p className="rec-description">{rec.description}</p>
                        </div>
                        <span className={`rec-status ${rec.resolved ? 'complete' : 'open'}`}>
                          {rec.resolved ? 'Resolved' : 'Needs Attention'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {combinedRecommendations && combinedRecommendations.length > 0 && (
                <div className="recommendation-panel">
                  <h4>New Recommendations</h4>
                  <ul>
                    {combinedRecommendations.map((rec) => (
                      <li key={rec.rec_id}>
                        <strong>{rec.title}</strong> — {rec.description}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>

        <div className="modal-actions sticky">
          <button className="btn-secondary" onClick={onClose}>Close</button>
          <button className="btn-primary" onClick={onViewVersion}>
            View Full Version
          </button>
        </div>
      </div>
    </div>
  );
}
