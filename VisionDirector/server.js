
const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 8080;

// Serve static files from the current directory
app.use(express.static(__dirname));

// Route for the main application
app.get('*', (req, res) => {
  const indexPath = path.join(__dirname, 'index.html');
  
  fs.readFile(indexPath, 'utf8', (err, data) => {
    if (err) {
      return res.status(500).send('Error loading index.html');
    }

    // Securely inject the API_KEY into a browser-friendly process.env shim.
    // NOTE: module scripts do not get Node's process object, so we create a global one.
    const apiKey = process.env.API_KEY || '';
    const apiKeyLiteral = JSON.stringify(apiKey);
    const envShim = `<script>var process = { env: { API_KEY: ${apiKeyLiteral} } }; window.process = process;</script>`;
    
    // Inject the shim before the other scripts
    const result = data.replace('<head>', `<head>\n  ${envShim}`);
    
    res.send(result);
  });
});

app.listen(PORT, () => {
  console.log(`VisionDirector Elite is active on port ${PORT}`);
});
