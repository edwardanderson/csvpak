local M = {}

-- ---------------------------------------------------------------------------
-- Paths
-- ---------------------------------------------------------------------------

local function sanitize_identifier(value)
  local safe = tostring(value or 'csvpak')
  safe = safe:gsub('^.+/', '')
  safe = safe:gsub('[^%w%-_]+', '-')
  if safe == '' then safe = 'csvpak' end
  return safe
end

function M.app_identifier()
  if _G.CSVPAK_APP_ID == nil then
    local exe = arg and arg[-1] or nil
    _G.CSVPAK_APP_ID = sanitize_identifier(exe)
  end
  return _G.CSVPAK_APP_ID
end

function M.runtime_db_path()
  local override = os.getenv('CSVPAK_DB_PATH')
  if override and override ~= '' then return override end
  return '/tmp/' .. M.app_identifier() .. '-data.sqlite'
end

function M.dirty_marker_path()
  return '/tmp/' .. M.app_identifier() .. '-dirty'
end

function M.status_file_path()
  return '/tmp/' .. M.app_identifier() .. '-status'
end

-- ---------------------------------------------------------------------------
-- File helpers
-- ---------------------------------------------------------------------------

function M.copy_file(src, dst)
  local f = io.open(src, 'rb')
  if not f then return false end
  local data = f:read('*a')
  f:close()
  local g = io.open(dst, 'wb')
  if not g then return false end
  g:write(data)
  g:close()
  return true
end

-- ---------------------------------------------------------------------------
-- Persistent status (survives across worker processes via a tmp file)
-- ---------------------------------------------------------------------------

function M.write_status(status, message)
  local f = io.open(M.status_file_path(), 'wb')
  if not f then return false end
  f:write((status or 'ready') .. '\n' .. (message or ''))
  f:close()
  return true
end

function M.read_status()
  local f = io.open(M.status_file_path(), 'rb')
  if not f then
    return 'ready', 'Changes are staged in a temporary SQLite file. Click "Exit and save" to embed them into the distributable.'
  end
  local content = f:read('*a')
  f:close()
  local status, message = content:match('^([^\n]*)\n?(.*)$')
  if not status or status == '' then status = 'ready' end
  if not message or message == '' then
    message = 'Changes are staged in a temporary SQLite file. Click "Exit and save" to embed them into the distributable.'
  end
  return status, message
end

function M.read_app_title()
  local f = io.open('/zip/.app_title', 'rb')
  if not f then return 'csvpak editor' end
  local title = f:read('*a')
  f:close()
  if not title or title == '' then
    return 'csvpak editor'
  end
  return title
end

-- ---------------------------------------------------------------------------
-- Dirty tracking
-- ---------------------------------------------------------------------------

function M.mark_db_dirty()
  local f = io.open(M.dirty_marker_path(), 'wb')
  if f then f:write('dirty'); f:close() end
  M.write_status('pending',
    'Unsaved changes are staged locally. Click "Exit and save" to embed them into the distributable.')
end

function M.has_pending_changes()
  local f = io.open(M.dirty_marker_path(), 'rb')
  if not f then return false end
  f:close()
  return true
end

function M.clear_pending_changes()
  os.remove(M.dirty_marker_path())
end

-- ---------------------------------------------------------------------------
-- Database initialisation
-- ---------------------------------------------------------------------------

function M.initialise_db()
  local path = M.runtime_db_path()
  local build_id_path = '/tmp/' .. M.app_identifier() .. '-build_id'

  -- Check if the archive's build ID matches the temp database's.
  -- If not, invalidate the temp database (it's from a different build).
  local archive_build_id = nil
  do
    local f = io.open('/zip/.build_id', 'rb')
    if f then
      archive_build_id = f:read('*a')
      f:close()
    end
  end

  local local_build_id = nil
  do
    local f = io.open(build_id_path, 'rb')
    if f then
      local_build_id = f:read('*a')
      f:close()
    end
  end

  -- If build IDs don't match, delete stale temp database and recopy from archive.
  if archive_build_id and local_build_id ~= archive_build_id then
    os.remove(path)
  end

  -- Only seed from the archive if the temp file does not yet exist.
  local existing = io.open(path, 'rb')
  if existing then
    existing:close()
  else
    M.copy_file('/zip/data.sqlite', path)
    -- Write the build ID marker so we know which archive this temp file came from.
    if archive_build_id then
      local f = io.open(build_id_path, 'wb')
      if f then f:write(archive_build_id); f:close() end
    end
    M.write_status('ready',
      'Changes are staged in a temporary SQLite file. Click "Exit and save" to embed them into the distributable.')
  end

  local handle = sqlite3.open(path)
  assert(handle, 'Failed to open runtime SQLite database at ' .. path)
  return handle
end

-- ---------------------------------------------------------------------------
-- StoreAsset persistence
-- ---------------------------------------------------------------------------

function M.persist_db_to_archive()
  local path = M.runtime_db_path()
  local content = Slurp(path)
  if not content then
    M.write_status('error', 'Unable to read runtime SQLite file: ' .. path)
    return false
  end

  local ok, err = pcall(StoreAsset, '/data.sqlite', content, 0644)
  if ok then
    M.clear_pending_changes()
    M.write_status('ok', 'SQLite database was embedded into the distributable archive successfully.')
    return true
  end

  M.write_status('error', 'StoreAsset failed: ' .. tostring(err))
  return false
end

-- ---------------------------------------------------------------------------
-- Ensure globals (called at the top of every route so .init.lua state is
-- not required — redbean may not run .init.lua in every worker process).
-- ---------------------------------------------------------------------------

function M.ensure_globals()
  if sqlite3 == nil then
    sqlite3 = require('lsqlite3')
  end

  if COLUMNS == nil then
    COLUMNS = dofile('/zip/columns.lua')
  end

  if db == nil then
    db = M.initialise_db()
  end

  -- Refresh status globals so templates can read them without side effects.
  local status, message = M.read_status()
  _G.CSVPAK_STATUS = status
  _G.CSVPAK_STATUS_MESSAGE = message
  _G.CSVPAK_APP_TITLE = M.read_app_title()

  -- Expose helpers as simple globals.
  _G.mark_db_dirty = function() M.mark_db_dirty() end
  _G.persist_db_to_archive = function() return M.persist_db_to_archive() end
end

return M
