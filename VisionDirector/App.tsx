import React, { useEffect, useState } from "react";
import Studio from "./components/Studio";
import ErrorBoundary from "./components/ErrorBoundary";
import { warmRuntimeKeys, purgeLegacyLocalStorageKeys } from "./services/runtimeKeys";

const App: React.FC = () => {
  const [isBridgeMode, setIsBridgeMode] = useState(false);

  useEffect(() => {
    // Critical: remove any old browser-stored keys (your rule: delete means void).
    purgeLegacyLocalStorageKeys();

    // Pull keys from DB into memory (NOT persistent storage).
    warmRuntimeKeys();

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
