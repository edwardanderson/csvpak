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
    <main class="container">
      ]] .. body .. [[
    </main>
  </body>
</html>
]]
end

ProgramHeader('Content-Type', 'text/html; charset=utf-8')

local id = GetParam('id')
local existing = nil

if id and id ~= '' then
  for row in db:nrows('SELECT rowid as _rowid, * FROM data WHERE rowid = ' .. tostring(tonumber(id) or 0) .. ' LIMIT 1') do
    existing = {}
    for _, col in ipairs(COLUMNS) do
      existing[col.name] = row[col.name]
    end
    existing._rowid = id
    break
  end
end

if GetMethod() == 'POST' then
  local names = {}
  local values = {}

  for _, col in ipairs(COLUMNS) do
    table.insert(names, col.name)
    local raw = GetParam(col.name)
    if col.html_input_type == 'checkbox' then
      table.insert(values, (raw and raw ~= '') and 1 or 0)
    else
      table.insert(values, (raw == '' or raw == nil) and nil or raw)
    end
  end

  if id and id ~= '' then
    local assignments = {}
    for _, name in ipairs(names) do
      table.insert(assignments, '"' .. name .. '" = ?')
    end
    local stmt = db:prepare('UPDATE data SET ' .. table.concat(assignments, ', ') .. ' WHERE rowid = ?')
    for i, v in ipairs(values) do stmt:bind(i, v) end
    stmt:bind(#values + 1, id)
    stmt:step()
    stmt:finalize()
  else
    local quoted, placeholders = {}, {}
    for _, name in ipairs(names) do
      table.insert(quoted, '"' .. name .. '"')
      table.insert(placeholders, '?')
    end
    local stmt = db:prepare('INSERT INTO data (' .. table.concat(quoted, ', ') .. ') VALUES (' .. table.concat(placeholders, ', ') .. ')')
    for i, v in ipairs(values) do stmt:bind(i, v) end
    stmt:step()
    stmt:finalize()
  end

  mark_db_dirty()
  SetStatus(303)
  SetHeader('Location', '/index.lua')
  Write('')
  return
end

-- Build form fields.
local fields = ''
for _, col in ipairs(COLUMNS) do
  local value = ''
  if existing and existing[col.name] ~= nil then
    value = tostring(existing[col.name])
  elseif col.default ~= nil then
    value = tostring(col.default)
  end

  local req = col.required and 'required' or ''

  if #col.enum_values > 0 then
    local opts = ''
    for _, opt in ipairs(col.enum_values) do
      local sel = (value == tostring(opt)) and 'selected' or ''
      opts = opts .. '<option ' .. sel .. ' value="' .. EscapeHtml(tostring(opt)) .. '">' .. EscapeHtml(tostring(opt)) .. '</option>'
    end
    fields = fields .. '<label>' .. EscapeHtml(col.title) .. '<select name="' .. col.name .. '" ' .. req .. '>' .. opts .. '</select></label>'
  elseif col.html_input_type == 'checkbox' then
    local checked = (value == '1' or value == 'true') and 'checked' or ''
    fields = fields .. '<label><input type="checkbox" name="' .. col.name .. '" value="1" ' .. checked .. ' /> ' .. EscapeHtml(col.title) .. '</label>'
  else
    fields = fields .. '<label>' .. EscapeHtml(col.title) .. '<input type="' .. col.html_input_type .. '" name="' .. col.name .. '" value="' .. EscapeHtml(value) .. '" ' .. req .. ' /></label>'
  end
end

local delete_form = ''
if id and id ~= '' then
  delete_form = '<form method="post" action="/delete.lua"><input type="hidden" name="id" value="' .. EscapeHtml(id) .. '" /><button type="submit" class="contrast">Delete</button></form>'
end

local body = '<h1>' .. (id and id ~= '' and 'Edit record' or 'New record') .. '</h1>' ..
  '<form method="post" action="/record.lua">' ..
  '<input type="hidden" name="id" value="' .. EscapeHtml(id or '') .. '" />' ..
  fields ..
  '<p><button type="submit">Save</button> <a href="/index.lua" role="button" class="secondary outline">Cancel</a></p>' ..
  '</form>' .. delete_form

Write(render_page('Record', body))
