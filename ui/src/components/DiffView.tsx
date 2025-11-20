import type { DiffResponse } from '../api/client';
import './DiffView.css';

interface DiffViewProps {
  diff: DiffResponse;
}

export default function DiffView({ diff }: DiffViewProps) {
  return (
    <div className="diff-view">
      <div className="diff-summary">
        <h4>Summary</h4>
        <p>{diff.summary}</p>
      </div>

      {diff.structure && (
        <div className="diff-section">
          <h4>Structure Changes</h4>
          {diff.structure.added_classes && diff.structure.added_classes.length > 0 && (
            <div className="diff-group">
              <h5>Added Classes ({diff.structure.added_classes.length})</h5>
              <ul>
                {diff.structure.added_classes.map((cls: any, idx: number) => (
                  <li key={idx} className="diff-added">+ {cls.name}</li>
                ))}
              </ul>
            </div>
          )}
          {diff.structure.removed_classes && diff.structure.removed_classes.length > 0 && (
            <div className="diff-group">
              <h5>Removed Classes ({diff.structure.removed_classes.length})</h5>
              <ul>
                {diff.structure.removed_classes.map((cls: any, idx: number) => (
                  <li key={idx} className="diff-removed">- {cls.name}</li>
                ))}
              </ul>
            </div>
          )}
          {diff.structure.changed_classes && diff.structure.changed_classes.length > 0 && (
            <div className="diff-group">
              <h5>Modified Classes ({diff.structure.changed_classes.length})</h5>
              <ul>
                {diff.structure.changed_classes.map((cls: any, idx: number) => (
                  <li key={idx} className="diff-changed">
                    ~ {cls.name}
                    {cls.details && <span className="diff-details"> ({cls.details})</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {diff.metrics && Object.keys(diff.metrics).length > 0 && (
        <div className="diff-section">
          <h4>Metrics Changes</h4>
          <table className="metrics-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Before</th>
                <th>After</th>
                <th>Change</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(diff.metrics).map(([key, value]: [string, any]) => (
                <tr key={key}>
                  <td>{key}</td>
                  <td>{value.before ?? 'N/A'}</td>
                  <td>{value.after ?? 'N/A'}</td>
                  <td className={value.change > 0 ? 'positive' : value.change < 0 ? 'negative' : ''}>
                    {value.change > 0 ? '+' : ''}{value.change}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {diff.findings && (
        <div className="diff-section">
          <h4>Findings Changes</h4>
          {diff.findings.new_findings && diff.findings.new_findings.length > 0 && (
            <div className="diff-group">
              <h5>New Issues ({diff.findings.new_findings.length})</h5>
              <ul>
                {diff.findings.new_findings.map((finding: any, idx: number) => (
                  <li key={idx} className="diff-added">
                    <strong>{finding.severity}:</strong> {finding.issue}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {diff.findings.resolved_findings && diff.findings.resolved_findings.length > 0 && (
            <div className="diff-group">
              <h5>Resolved Issues ({diff.findings.resolved_findings.length})</h5>
              <ul>
                {diff.findings.resolved_findings.map((finding: any, idx: number) => (
                  <li key={idx} className="diff-removed">
                    <strong>{finding.severity}:</strong> {finding.issue}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
