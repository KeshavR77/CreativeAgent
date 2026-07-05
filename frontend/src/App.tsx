import { Routes, Route } from 'react-router-dom';
import ProjectList from './views/ProjectList';
import Studio from './views/Studio';
import Cockpit from './views/Cockpit';
import Export from './views/Export';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectList />} />
      <Route path="/studio" element={<Studio />} />
      <Route path="/studio/:id" element={<Studio />} />
      <Route path="/cockpit" element={<Cockpit />} />
      <Route path="/cockpit/:id" element={<Cockpit />} />
      <Route path="/export" element={<Export />} />
      <Route path="/export/:id" element={<Export />} />
    </Routes>
  );
}
