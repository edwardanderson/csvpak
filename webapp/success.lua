local runtime = require('csvpak_runtime')
runtime.ensure_globals()

local function render_page(title, body)
  return [[
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>]] .. title .. [[</title>
    <link rel="stylesheet" href="/static/pico.min.css" />
    <link rel="stylesheet" href="/static/style.css" />
  </head>
  <body>
    <main class="container">
      ]] .. body .. [[
    </main>
  </body>
</html>
]]
end

ProgramHeader('Content-Type', 'text/html; charset=utf-8')

local body = [[
<article>
  <h1>✓ Changes saved</h1>
  <p>Your data has been successfully written to the archive.</p>
  <p>You can now close this browser tab or shut down the server.</p>
  <form id="shutdown-form" method="post" action="/shutdown.lua" style="display: none;">
    <input type="hidden" name="confirm" value="yes" />
  </form>
  <button id="shutdown-btn" type="button" class="contrast">Shut down server</button>
  <div id="status" style="margin-top: 1.5rem; display: none; text-align: center;">
    <p id="status-msg" style="color: #555; font-size: 0.95rem;">Shutting down server...</p>
  </div>
</article>

<script>
document.getElementById('shutdown-btn').addEventListener('click', function() {
  const btn = this;
  const statusDiv = document.getElementById('status');
  const statusMsg = document.getElementById('status-msg');
  
  btn.disabled = true;
  btn.style.opacity = '0.6';
  statusDiv.style.display = 'block';
  
  document.getElementById('shutdown-form').submit();
  
  // Poll the server every 500ms
  let attempts = 0;
  const maxAttempts = 60; // Give it up to 30 seconds
  
  const poll = setInterval(() => {
    attempts++;
    
    fetch('/', { method: 'HEAD' })
      .then(response => {
        // Server is still responding
        statusMsg.textContent = 'Waiting for server to shut down...';
      })
      .catch(error => {
        // Server is down (connection refused or similar)
        clearInterval(poll);
        statusMsg.innerHTML = '<strong>✓ Server shut down successfully</strong>';
        statusMsg.style.color = '#2e7d32';
      });
    
    if (attempts >= maxAttempts) {
      clearInterval(poll);
      statusMsg.innerHTML = '<strong>Server shutdown timeout</strong>';
      statusMsg.style.color = '#d32f2f';
      btn.disabled = false;
      btn.style.opacity = '1';
    }
  }, 500);
});
</script>
]]

Write(render_page('Success', body))
