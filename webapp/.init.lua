sqlite3 = require('lsqlite3')
runtime = require('csvpak_runtime')

if not COLUMNS then
  COLUMNS = dofile('/zip/columns.lua')
end

runtime.ensure_globals()

function render_page(title, body)
  return [[
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>]] .. title .. [[</title>
    <link rel="stylesheet" href="/static/style.css" />
    <script src="/static/htmx.min.js"></script>
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
