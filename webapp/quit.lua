local runtime = require('csvpak_runtime')
runtime.ensure_globals()

if GetMethod() ~= 'POST' then
  SetStatus(405)
  Write('Method not allowed')
  return
end

-- Plain exit should not delete the temporary database.
-- The temporary runtime DB is intentionally preserved so users can resume
-- their staged changes in a later session.

SetStatus(200)
SetHeader('Content-Type', 'text/html; charset=utf-8')

local page = [[
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Server Shutting Down</title>
    <link rel="stylesheet" href="/static/pico.min.css" />
    <link rel="stylesheet" href="/static/style.css" />
  </head>
  <body>
    <main class="container">
      <article>
        <h1 id="title">Shutting Down Server</h1>
        <p id="status">Waiting for server to shut down...</p>
        <progress id="progress" aria-label="Shutting down"></progress>
      </article>
    </main>
  </body>
</html>

<script>
const title = document.getElementById('title');
const status = document.getElementById('status');
const progress = document.getElementById('progress');

let attempts = 0;
const maxAttempts = 60; // 30 seconds at 500ms polling

function checkServer() {
  attempts++;

  fetch('/', { method: 'HEAD' })
    .then(response => {
      status.textContent = 'Waiting for server to shut down...';
    })
    .catch(error => {
      clearInterval(pollInterval);
      progress.hidden = true;
      title.textContent = '✓ Server Shut Down';
      status.textContent = 'Server has been shut down successfully.';
    });

  if (attempts >= maxAttempts) {
    clearInterval(pollInterval);
    progress.hidden = true;
    title.textContent = 'Shutdown Timeout';
    status.textContent = 'Server did not shut down within the expected time.';
  }
}

const pollInterval = setInterval(checkServer, 500);
checkServer();
</script>
]]

Write(page)

local unix = require 'unix'
unix.kill(unix.getppid(), unix.SIGTERM)
