local runtime = require('csvpak_runtime')
runtime.ensure_globals()

if GetMethod() ~= 'POST' then
  SetStatus(405)
  Write('Method not allowed')
  return
end

persist_db_to_archive()

-- Remove the temporary database file
local db_path = runtime.runtime_db_path()
os.remove(db_path)

SetStatus(303)
SetHeader('Location', '/success.lua')
Write('')