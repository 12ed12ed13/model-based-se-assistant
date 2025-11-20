import { useState } from 'react';
import './CodeViewer.css';

interface CodeViewerProps {
  code: Record<string, any>;
  tests: Record<string, any>;
}

export default function CodeViewer({ code, tests }: CodeViewerProps) {
  const [selectedFile, setSelectedFile] = useState<any>(null);
  const [activeSection, setActiveSection] = useState<'code' | 'tests'>('code');

  const codeFiles = code?.files || [];
  const testFiles = tests?.test_files || [];

  const currentFiles = activeSection === 'code' ? codeFiles : testFiles;

  return (
    <div className="code-viewer">
      <div className="code-viewer-nav">
        <div className="section-tabs">
          <button
            className={activeSection === 'code' ? 'active' : ''}
            onClick={() => {
              setActiveSection('code');
              setSelectedFile(null);
            }}
          >
            Source Code ({codeFiles.length})
          </button>
          <button
            className={activeSection === 'tests' ? 'active' : ''}
            onClick={() => {
              setActiveSection('tests');
              setSelectedFile(null);
            }}
          >
            Tests ({testFiles.length})
          </button>
        </div>
        <div className="file-list">
          {currentFiles.length === 0 ? (
            <div className="empty-state-small">{activeSection === 'code' ? 'Generating code...' : 'Generating tests...'}</div>
          ) : (
            <>
              {currentFiles.map((file: any, idx: number) => (
                <button
                  key={idx}
                  className={`file-item ${selectedFile === file ? 'active' : ''}`}
                  onClick={() => setSelectedFile(file)}
                >
                  {file.path}
                </button>
              ))}
            </>
          )}
        </div>
      </div>
      <div className="code-viewer-content">
        {selectedFile ? (
          <div>
            <div className="file-header">
              <h4>{selectedFile.path}</h4>
              <button
                className="btn-secondary"
                onClick={() => {
                  navigator.clipboard.writeText(selectedFile.content);
                  alert('Code copied to clipboard!');
                }}
              >
                Copy
              </button>
            </div>
            <pre className="code-content">{selectedFile.content}</pre>
          </div>
        ) : (
          <div className="empty-state">
            <p>Select a file to view its contents</p>
          </div>
        )}
      </div>
    </div>
  );
}
