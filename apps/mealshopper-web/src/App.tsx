import { useEffect, useState } from 'react';
import { DealDiscoveryPage } from './pages/DealDiscoveryPage';
import { HomePage } from './pages/HomePage';

function App() {
  const [pathname, setPathname] = useState(window.location.pathname);

  useEffect(() => {
    const updatePathname = () => setPathname(window.location.pathname);
    window.addEventListener('popstate', updatePathname);
    return () => window.removeEventListener('popstate', updatePathname);
  }, []);

  if (pathname === '/discover') {
    return <DealDiscoveryPage />;
  }

  return <HomePage />;
}

export default App;