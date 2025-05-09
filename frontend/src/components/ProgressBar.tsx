import React from 'react';
import './ProgressBar.css';

const ProgressBar = ({ progress }: { progress: number }) => (
  <div className="progress-bar-container">
    <div className="progress-bar" style={{ width: `${progress}%` }} />
    <span className="progress-label">{Math.round(progress)}%</span>
  </div>
);

export default ProgressBar; 