local runtime = require('csvpak_runtime')
runtime.ensure_globals()

local cursor = tonumber(GetParam('cursor')) or nil
local limit = tonumber(GetParam('limit')) or 25

ProgramHeader('Content-Type', 'text/html; charset=utf-8')

-- Keyset pagination: fetch rows with rowid < cursor, ordered DESC
local rows = {}
if cursor then
  local query = 'SELECT rowid as _rowid, * FROM data WHERE rowid < ' .. tostring(cursor) .. ' ORDER BY rowid DESC LIMIT ' .. tostring(limit + 1)
  for row in db:nrows(query) do
    table.insert(rows, row)
  end
else
  local query = 'SELECT rowid as _rowid, * FROM data ORDER BY rowid DESC LIMIT ' .. tostring(limit + 1)
  for row in db:nrows(query) do
    table.insert(rows, row)
  end
end

-- Render table rows
local html = ''
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
  html = html .. '<tr>' .. cells .. '<td><a href="/record.lua?id=' .. tostring(row._rowid) .. '">Edit</a></td></tr>'
end

-- Add sentinel row if there are more rows
if has_more then
  local next_cursor = rows[limit]._rowid
  html = html .. '<tr id="load-more-' .. tostring(next_cursor) .. '" hx-get="/rows.lua?cursor=' .. tostring(next_cursor) .. '&limit=' .. tostring(limit) .. '" ' ..
    'hx-target="closest tr" hx-swap="outerHTML" hx-trigger="csvpak-load-more once"><td colspan="99">Loading...</td></tr>'
end

Write(html)
