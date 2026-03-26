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
    <script src="/static/htmx.min.js"></script>
  </head>
  <body>
    <main class="container-fluid">
      ]] .. body .. [[
    </main>
    <script>
      (function () {
        function nearBottom(container) {
          return (container.scrollTop + container.clientHeight) >= (container.scrollHeight - 12);
        }

        function triggerLoadMore() {
          var container = document.getElementById('rows-container');
          if (!container) return;
          if (!nearBottom(container)) return;

          var sentinel = container.querySelector('tr[id^="load-more-"]');
          if (!sentinel) return;
          if (sentinel.classList.contains('htmx-request')) return;

          htmx.trigger(sentinel, 'csvpak-load-more');
        }

        document.addEventListener('DOMContentLoaded', function () {
          var container = document.getElementById('rows-container');
          if (!container) return;
          container.addEventListener('scroll', triggerLoadMore, { passive: true });
        });
      })();
    </script>
  </body>
</html>
]]
end

ProgramHeader('Content-Type', 'text/html; charset=utf-8')

local limit = 25
local rows = {}
local query = 'SELECT rowid as _rowid, * FROM data ORDER BY rowid DESC LIMIT ' .. tostring(limit + 1)
for row in db:nrows(query) do
  table.insert(rows, row)
end

local header_cells = ''
for _, col in ipairs(COLUMNS) do
  header_cells = header_cells .. '<th>' .. EscapeHtml(col.title) .. '</th>'
end

local body_rows = ''
local has_more = #rows > limit
local display_count = has_more and limit or #rows

for i = 1, display_count do
  local row = rows[i]
  local cells = ''
  for _, col in ipairs(COLUMNS) do
    local v = row[col.name]
    if v == nil then v = '' end
    cells = cells .. '<td>' .. EscapeHtml(tostring(v)) .. '</td>'
  end
  body_rows = body_rows .. '<tr>' .. cells .. '<td><a href="/record.lua?id=' .. tostring(row._rowid) .. '">Edit</a></td></tr>'
end

if body_rows == '' then
  body_rows = '<tr><td colspan="99">No rows.</td></tr>'
end

-- Add sentinel row for pagination if there are more rows
if has_more then
  local next_cursor = rows[limit]._rowid
  body_rows = body_rows .. '<tr id="load-more-' .. tostring(next_cursor) .. '" hx-get="/rows.lua?cursor=' .. tostring(next_cursor) .. '&limit=' .. tostring(limit) .. '" ' ..
    'hx-target="closest tr" hx-swap="outerHTML" hx-trigger="csvpak-load-more once"><td colspan="99">Loading...</td></tr>'
end

local body = [[
<h1>]] .. EscapeHtml(CSVPAK_APP_TITLE or 'csvpak editor') .. [[</h1>
<p>
  <a href="/record.lua" role="button" class="secondary outline">New record</a>
</p>
<div class="overflow-auto" id="rows-container">
<table>
  <thead>
    <tr>]] .. header_cells .. [[<th>Actions</th></tr>
  </thead>
  <tbody id="rows-body">]] .. body_rows .. [[</tbody>
</table>
</div>
<footer>
  <div class="footer-actions">
    <form method="post" action="/quit.lua">
      <button type="submit" class="secondary outline">Exit</button>
    </form>
    <form method="post" action="/exit.lua">
      <button type="submit">Package data and exit</button>
    </form>
  </div>
</footer>
]]

Write(render_page('csvpak', body))
