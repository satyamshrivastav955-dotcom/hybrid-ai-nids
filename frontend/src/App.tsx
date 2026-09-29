import React from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { Layout } from './layouts/Layout';
import Dashboard from './pages/Dashboard';
import LiveTraffic from './pages/LiveTraffic';
import Alerts from './pages/Alerts';
import AlertDetail from './pages/AlertDetail';
import AttackAnalysis from './pages/AttackAnalysis';
import NetworkMap from './pages/NetworkMap';
import Drift from './pages/Drift';
import ModelPerformance from './pages/ModelPerformance';
import ThreatIntel from './pages/ThreatIntel';
import Reports from './pages/Reports';
import SystemStatus from './pages/SystemStatus';
import Settings from './pages/Settings';
import './styles.css';

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/traffic', element: <LiveTraffic /> },
      { path: '/alerts', element: <Alerts /> },
      { path: '/alerts/:uid', element: <AlertDetail /> },
      { path: '/attacks', element: <AttackAnalysis /> },
      { path: '/network', element: <NetworkMap /> },
      { path: '/drift', element: <Drift /> },
      { path: '/models', element: <ModelPerformance /> },
      { path: '/intel', element: <ThreatIntel /> },
      { path: '/reports', element: <Reports /> },
      { path: '/system', element: <SystemStatus /> },
      { path: '/settings', element: <Settings /> },
    ],
  },
]);

const App: React.FC = () => <RouterProvider router={router} />;
export default App;
