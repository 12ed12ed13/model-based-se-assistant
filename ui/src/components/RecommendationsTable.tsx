import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { RecommendationSummary } from '../api/client';
import { recommendationsApi } from '../api/client';
import './RecommendationsTable.css';

interface RecommendationsTableProps {
  recommendations: RecommendationSummary[];
  projectId: string;
}

export default function RecommendationsTable({ recommendations, projectId }: RecommendationsTableProps) {
  const queryClient = useQueryClient();
  const [expandedRec, setExpandedRec] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: ({ recId, status }: { recId: string; status: string }) =>
      recommendationsApi.update(projectId, recId, { status: status as any }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations', projectId] });
    },
  });

  if (recommendations.length === 0) {
    return <div className="empty-state">No recommendations for this version</div>;
  }

  return (
    <div className="recommendations-table">
      <table>
        <thead>
          <tr>
            <th>Priority</th>
            <th>Title</th>
            <th>Affected Entities</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {recommendations.map((rec) => (
            <>
              <tr key={rec.rec_id}>
                <td>
                  <span className={`priority-badge priority-${rec.priority}`}>
                    {rec.priority}
                  </span>
                </td>
                <td>
                  <button
                    className="title-button"
                    onClick={() => setExpandedRec(expandedRec === rec.rec_id ? null : rec.rec_id)}
                  >
                    {rec.title}
                  </button>
                </td>
                <td>
                  <span className="entity-list">
                    {rec.affected_entities.slice(0, 2).join(', ')}
                    {rec.affected_entities.length > 2 && ` +${rec.affected_entities.length - 2}`}
                  </span>
                </td>
                <td>
                  <select
                    value={rec.status}
                    onChange={(e) =>
                      updateMutation.mutate({ recId: rec.rec_id, status: e.target.value })
                    }
                    className={`status-select status-${rec.status}`}
                  >
                    <option value="open">Open</option>
                    <option value="in_progress">In Progress</option>
                    <option value="resolved">Resolved</option>
                    <option value="dismissed">Dismissed</option>
                  </select>
                </td>
                <td>
                  <button
                    className="btn-icon"
                    onClick={() => setExpandedRec(expandedRec === rec.rec_id ? null : rec.rec_id)}
                    title="Toggle details"
                  >
                    {expandedRec === rec.rec_id ? '▼' : '▶'}
                  </button>
                </td>
              </tr>
              {expandedRec === rec.rec_id && (
                <tr className="expanded-row">
                  <td colSpan={5}>
                    <div className="recommendation-details">
                      <p><strong>Description:</strong> {rec.description}</p>
                      {rec.design_pattern && (
                        <p><strong>Design Pattern:</strong> {rec.design_pattern}</p>
                      )}
                      {rec.rationale && (
                        <p><strong>Rationale:</strong> {rec.rationale}</p>
                      )}
                      <p><strong>Affected Entities:</strong> {rec.affected_entities.join(', ')}</p>
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
