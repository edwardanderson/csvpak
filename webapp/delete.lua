local runtime = require('csvpak_runtime')
runtime.ensure_globals()

if GetMethod() ~= 'POST' then
  SetStatus(405)
  Write('Method not allowed')
  return
end

local id = GetParam('id')
if id and id ~= '' then
  local stmt = db:prepare('DELETE FROM data WHERE rowid = ?')
  stmt:bind_values(id)
  stmt:step()
  stmt:finalize()
  mark_db_dirty()
end

SetStatus(303)
SetHeader('Location', '/index.lua')
Write('')
