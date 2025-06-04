import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ClientListPage from './pages/ClientListPage';
import ClientDetailPage from './pages/ClientDetailPage';

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<ClientListPage />} />
        <Route path="/client/:clientId" element={<ClientDetailPage />} />
      </Routes>
    </Router>
  );
};

export default App;
