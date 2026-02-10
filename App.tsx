import React, { useEffect, useState } from "react";
import Studio from "./components/Studio";
import ErrorBoundary from "./components/ErrorBoundary";

const App: React.FC = () => {
  const [isBridgeMode, setIsBridgeMode] = useState(false);

  useEffect(() => {
    try {
      const bridge = (window as any)?.aistudio;
      if (bridge) setIsBridgeMode(true);
    } catch {
      // ignore
    }
  }, []);

  return (
    <ErrorBoundary>
      <Studio isBridgeMode={isBridgeMode} />
    </ErrorBoundary>
  );
};

export default App;
