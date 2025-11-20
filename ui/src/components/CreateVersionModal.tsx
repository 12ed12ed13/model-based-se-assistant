import { useState } from 'react';
import type { CreateVersionRequest, RecommendationSummary } from '../api/client';
import './CreateVersionModal.css';

interface CreateVersionModalProps {
  onClose: () => void;
  onSubmit: (data: CreateVersionRequest) => void;
  initialModelText?: string;
  initialModelFormat?: 'plantuml' | 'mermaid' | 'text';
  recommendations?: RecommendationSummary[];
}

export default function CreateVersionModal({
  onClose,
  onSubmit,
  initialModelText = '',
  initialModelFormat = 'plantuml',
  recommendations = [],
}: CreateVersionModalProps) {
  const [modelText, setModelText] = useState(initialModelText);
  const [modelFormat, setModelFormat] = useState<'plantuml' | 'mermaid' | 'text'>(initialModelFormat);
  const [description, setDescription] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      model_text: modelText,
      model_format: modelFormat,
      description: description || '',
    });
  };

  const examplePlantUML = `@startuml
class User {
  +id: int
  +name: string
  +email: string
}

class Order {
  +id: int
  +amount: decimal
  +status: string
}

User "1" -- "*" Order : places
@enduml`;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`modal-content modal-large ${recommendations.length > 0 ? 'has-recommendations' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Version</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body-container">
          <form onSubmit={handleSubmit} className="modal-form">
            <div className="form-group">
              <label htmlFor="modelFormat">Model Format</label>
              <select
                id="modelFormat"
                value={modelFormat}
                onChange={(e) => setModelFormat(e.target.value as any)}
              >
                <option value="plantuml">PlantUML</option>
                <option value="mermaid">Mermaid</option>
                <option value="text">Text</option>
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="modelText">Model Text *</label>
              <textarea
                id="modelText"
                value={modelText}
                onChange={(e) => setModelText(e.target.value)}
                placeholder={examplePlantUML}
                rows={20}
                required
                className="code-textarea"
              />
            </div>
            <div className="form-group">
              <label htmlFor="description">Description</label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What changed in this version?"
                rows={3}
              />
            </div>
            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn-primary">
                Create Version
              </button>
            </div>
          </form>

          {recommendations.length > 0 && (
            <div className="recommendations-panel">
              <h3>Recommendations from Previous Version</h3>
              <div className="recommendations-list">
                {recommendations.map((rec) => (
                  <div key={rec.rec_id} className={`recommendation-card priority-${rec.priority}`}>
                    <div className="rec-header">
                      <span className="rec-priority">{rec.priority}</span>
                      <span className="rec-title">{rec.title}</span>
                    </div>
                    <p className="rec-description">{rec.description}</p>
                    {rec.rationale && <p className="rec-rationale"><strong>Rationale:</strong> {rec.rationale}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
