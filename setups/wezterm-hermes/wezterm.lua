-- Extracted from a daily Windows setup; private paths and session state omitted.
-- Edit these settings for your installation. No installer changes your live setup.
local wezterm = require 'wezterm'
local config = wezterm.config_builder()
local hermes = 'hermes' -- Or the absolute path to your hermes.exe.
local hermes_home = os.getenv('HERMES_HOME') or (wezterm.home_dir .. '/.hermes')
local git_bash = { 'C:/Program Files/Git/bin/bash.exe', '-l' }
local powershell = { 'powershell.exe', '-NoLogo' }
local state_file = hermes_home .. '/wezterm-tabs.json'
local crumbs_dir = hermes_home .. '/terminal-sessions/'

config.default_prog = { hermes }
config.default_cwd = wezterm.home_dir
config.set_environment_variables = { HERMES_HOME = hermes_home }
config.check_for_updates = false
config.scrollback_lines = 5000
config.font_size = 11
config.initial_cols = 120
config.initial_rows = 32
config.status_update_interval = 1000
config.use_fancy_tab_bar = false
config.tab_max_width = 24
config.hide_tab_bar_if_only_one_tab = false
config.launch_menu = {
  { label = 'Hermes', args = { hermes } },
  { label = 'Git Bash', args = git_bash },
  { label = 'PowerShell', args = powershell },
}

wezterm.on('format-tab-title', function(tab)
  local title = tab.active_pane.title
  if title:lower():find('python') or title:lower():find('hermes') then title = 'Hermes' end
  return ' ' .. (tab.tab_index + 1) .. ': ' .. title .. ' '
end)

local function json_encode(value)
  if wezterm.serde then return wezterm.serde.json_encode(value) end
  return wezterm.json_encode(value)
end

local function json_decode(value)
  if wezterm.serde then return wezterm.serde.json_decode(value) end
  return wezterm.json_parse(value)
end

local function read_file(path)
  local file = io.open(path, 'r')
  if not file then return nil end
  local contents = file:read('*a')
  file:close()
  return contents
end

local function valid_session(value)
  return type(value) == 'string' and #value > 0 and #value <= 256
    and value:match('^[%w_.-]+$') ~= nil
end

local function live_session(pane_id, first_seen)
  local raw = read_file(crumbs_dir .. 'wezterm_pane-' .. pane_id)
  if not raw then return nil end
  local ok, data = pcall(json_decode, raw)
  if not ok or type(data) ~= 'table' or not valid_session(data.session_id)
    or type(data.ts) ~= 'number' then return nil end
  -- Pane IDs are reused after restart; an old breadcrumb is not a live session.
  if data.ts + 5 < first_seen then return nil end
  return data.session_id
end

local function tab_entry(pane)
  local id = tostring(pane:pane_id())
  local seen = wezterm.GLOBAL.tab_first_seen or {}
  local first = seen[id]
  if not first then
    -- A hot config reload has existing panes but no gui-startup in this context.
    first = wezterm.GLOBAL.restored and os.time() or 0
    local copy = {}
    for key, value in pairs(seen) do copy[key] = value end
    copy[id] = first
    wezterm.GLOBAL.tab_first_seen = copy
  end
  local restored = wezterm.GLOBAL.restored or {}
  local session = live_session(id, first) or restored[id]
  if session then return { kind = 'hermes', session = session } end
  local process = (pane:get_foreground_process_name() or ''):lower()
  if process:find('hermes') or process:find('python') then return { kind = 'hermes' } end
  if process:find('bash') then return { kind = 'bash' } end
  if process:find('powershell') or process:find('pwsh') then return { kind = 'powershell' } end
  return { kind = 'hermes' }
end

local function save_tabs()
  local windows = {}
  for _, window in ipairs(wezterm.mux.all_windows()) do
    local tabs = {}
    for _, tab in ipairs(window:tabs()) do
      for _, info in ipairs(tab:panes_with_info()) do
        if info.is_active then table.insert(tabs, tab_entry(info.pane)) end
      end
    end
    if #tabs > 0 then table.insert(windows, tabs) end
  end
  if #windows == 0 then return end -- Keep the last snapshot during shutdown.
  local encoded = json_encode(windows)
  if encoded == wezterm.GLOBAL.last_saved then return end
  local file, err = io.open(state_file, 'w')
  if not file then error('Cannot save tab snapshot: ' .. tostring(err)) end
  local ok, write_err = file:write(encoded)
  file:close()
  if not ok then error('Cannot write tab snapshot: ' .. tostring(write_err)) end
  wezterm.GLOBAL.last_saved = encoded
end

local function args_for(entry)
  if entry.kind == 'bash' then return git_bash end
  if entry.kind == 'powershell' then return powershell end
  if entry.session then return { hermes, '--resume', entry.session } end
  return { hermes }
end

local function valid_snapshot(data)
  if type(data) ~= 'table' or #data == 0 then return false end
  for _, tabs in ipairs(data) do
    if type(tabs) ~= 'table' or #tabs == 0 then return false end
    for _, entry in ipairs(tabs) do
      if type(entry) ~= 'table' then return false end
      if entry.kind ~= 'hermes' and entry.kind ~= 'bash' and entry.kind ~= 'powershell' then
        return false
      end
      if entry.session ~= nil and (entry.kind ~= 'hermes' or not valid_session(entry.session)) then
        return false
      end
    end
  end
  return true
end

wezterm.on('update-status', function()
  local ok, err = pcall(save_tabs)
  if not ok then wezterm.log_error('tabs-restore: ' .. tostring(err)) end
end)

wezterm.on('gui-startup', function(cmd)
  local saved
  local raw = read_file(state_file)
  if raw and not cmd then
    local ok, data = pcall(json_decode, raw)
    if ok and valid_snapshot(data) then saved = data end
  end
  if not saved then
    wezterm.GLOBAL.restored = {}
    wezterm.mux.spawn_window(cmd or {})
    return
  end
  local restored = {}
  for _, tabs in ipairs(saved) do
    local window
    for i, entry in ipairs(tabs) do
      local pane, tab
      if i == 1 then
        tab, pane, window = wezterm.mux.spawn_window { args = args_for(entry) }
      else
        tab, pane = window:spawn_tab { args = args_for(entry) }
      end
      if entry.session then restored[tostring(pane:pane_id())] = entry.session end
    end
  end
  wezterm.GLOBAL.restored = restored
end)

return config
