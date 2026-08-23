import React from 'react';

export default function LibraryHeader({ eyebrow, title, description, action = null }) {
  return (
    <div className="history-header">
      <div>
        <div className="history-eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
