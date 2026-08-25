import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App.jsx';
import './design-tokens.css';
import './styles.css';
import './create-controls.css';
import './studio-polish.css';
import './mobile-touch-targets.css';

createRoot(document.getElementById('root')).render(<App />);
