import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ElectionListPage from './pages/ElectionList';
import HelpPage from './pages/Help';
import ElectionDashboardPage from './pages/ElectionDashboard';
import NotFoundPage from './pages/NotFoundPage';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<ElectionListPage />} />
        <Route path="/election/:id" element={<ElectionDashboardPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Router>
  );
}

export default App;