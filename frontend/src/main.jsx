import React from 'react';
import { createRoot } from 'react-dom/client';
import 'leaflet/dist/leaflet.css';
import './styles.css';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import ConnectionNotice from './components/ConnectionNotice';
createRoot(document.getElementById('root')).render(<React.StrictMode><ErrorBoundary><a className="skip-link" href="#main-content">본문으로 바로가기</a><ConnectionNotice/><App /></ErrorBoundary></React.StrictMode>);
