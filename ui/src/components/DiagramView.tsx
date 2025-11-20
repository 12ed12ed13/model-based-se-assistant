import { useQuery } from '@tanstack/react-query';
import { versionsApi } from '../api/client';
import './DiagramView.css';

interface DiagramViewProps {
  projectId: string;
  versionId: string;
}

export default function DiagramView({ projectId, versionId }: DiagramViewProps) {
  const { data: plantuml, isLoading, error } = useQuery({
    queryKey: ['plantuml', projectId, versionId],
    queryFn: async () => {
      const response = await versionsApi.getPlantUML(projectId, versionId);
      return response.data;
    },
  });

  const handleCopy = () => {
    if (plantuml) {
      navigator.clipboard.writeText(plantuml);
      alert('PlantUML copied to clipboard!');
    }
  };

  if (isLoading) {
    return <div className="loading">Loading diagram...</div>;
  }

  if (error) {
    return <div className="error">Error loading diagram: {String(error)}</div>;
  }

  if (!plantuml) {
    return <div className="empty-state">No diagram available</div>;
  }

  return (
    <div className="diagram-view">
      <div className="diagram-actions">
        <button className="btn-secondary" onClick={handleCopy}>
          Copy to Clipboard
        </button>
        <a
          href={`http://www.plantuml.com/plantuml/uml/${btoa(plantuml)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary"
        >
          View Rendered Diagram
        </a>
      </div>
      <pre className="diagram-code">{plantuml}</pre>
    </div>
  );
}
