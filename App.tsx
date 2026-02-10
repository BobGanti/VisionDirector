import React, { useEffect, useState } from "react";
import Studio from "./components/Studio";
import ErrorBoundary from "./components/ErrorBoundary";

const App: React.FC = () => {
  const [isBridgeMode, setIsBridgeMode] = useState(false);

  useEffect(() => {
    const bridge = (window as any).aistudio;
    if (bridge) setIsBridgeMode(true);
  }, []);

  return (
    <ErrorBoundary>
      <Studio isBridgeMode={isBridgeMode || !!(window as any).aistudio} />
    </ErrorBoundary>
  );
};

export default App;
