"""The page script behind the live feed: private data series inside a TradingView page.

TradingView Desktop 3.5 refuses every way of opening a tab over the debug port, so the
feed needs no tab and no chart. Each TradingView chart page already holds an open,
signed-in data connection (``chartApi``). ``JS_INSTALL`` puts one small object,
``window.__companionFeed``, into such a page. For every (symbol, resolution) the
companion wants, that object opens a *chart session of its own* on the page's connection
(the same thing TradingView does for each chart of a multi-chart layout), asks for one
series in it, and keeps the bars it is sent, including the live updates.

What this does and does not touch
---------------------------------
- It never calls anything on the page's charts: no symbol, resolution, layout, study,
  drawing, alert or setting is read through a setter or changed. The page's own chart
  sessions are separate objects with their own ids; messages are routed by session id.
- It adds: one global (``__companionFeed``), and one entry per series in the connection's
  session table. ``destroy()`` removes all of it; so does reloading the page.
- One series per session, always: a second ``create_series`` in a session is a critical
  error that makes TradingView drop and reopen that page's data connection.
- The series is only created after the symbol has resolved, so a wrong ticker ends as a
  plain ``symbol_error`` and nothing else.
- If the page's connection drops, the feed marks itself dead and forgets its sessions
  (the server already has); the bridge installs a fresh one.
- If nobody reads it for ``IDLE_MINUTES`` it removes itself, so a companion that was
  killed leaves nothing streaming.

Verified against TradingView Desktop 3.5.0 (Chrome 146) on 2026-11-12.
"""

from __future__ import annotations

import json

VERSION = 4  # 4: adds peek(). An older feed found in the page is replaced (its series reopen on the next read).
IDLE_MINUTES = 20

# Reads which chart a page shows and whether its data connection is usable. Changes nothing.
JS_PEEK = """
(function () {
  var out = {visible: document.visibilityState === 'visible', feed: false, connected: false};
  try {
    var api = window.TradingViewApi;
    var chart = api._activeChartWidgetWV.value();
    out.symbol = String(chart.symbol());
    out.resolution = String(chart.resolution());
    var link = chart._chartWidget.model().model().chartApi()._chartApi;
    out.connected = !!(link && link.connected() && typeof link.createSession === 'function'
                       && typeof link.chartCreateSession === 'function' && typeof link.resolveSymbol === 'function'
                       && typeof link.createSeries === 'function' && typeof link.requestMoreData === 'function');
    var feed = window.__companionFeed;
    out.feed = !!(feed && !feed.dead);
    if (feed) out.feed_series = Object.keys(feed.series || {}).length;
  } catch (e) { out.error = String((e && e.message) || e); }
  return out;
})()
"""

# The bars a page's own chart holds, for the diagnostic to compare against. Reads only.
JS_CHART_BARS = """
(function (count) {
  var chart = window.TradingViewApi._activeChartWidgetWV.value();
  var series = chart._chartWidget.model().mainSeries();
  var bars = series.bars();
  var rows = [];
  var last = bars.lastIndex();
  for (var i = Math.max(bars.firstIndex(), last - count + 1); i <= last; i++) {
    var v = bars.valueAt(i);
    if (v) rows.push([v[0], v[1], v[2], v[3], v[4], v[5] || 0]);
  }
  return {symbol: String(chart.symbol()), resolution: String(chart.resolution()), asked: String(series.getSymbolString()), rows: rows};
})(%d)
"""

# Installs (or finds) the feed object. Returns {ok, reused, version} or {ok: false, error}.
JS_INSTALL = """
(function (VERSION, IDLE_MS) {
  var old = window.__companionFeed;
  if (old && old.version === VERSION && !old.dead) { old.touched = Date.now(); return {ok: true, reused: true, series: Object.keys(old.series).length}; }
  if (old) { try { old.destroy(); } catch (e) {} }
  var link;
  try { link = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().model().chartApi()._chartApi; }
  catch (e) { return {ok: false, error: 'no_api', message: String((e && e.message) || e)}; }
  if (!link || !link.connected()) return {ok: false, error: 'not_connected'};

  var F = {version: VERSION, series: {}, dead: false, why: '', counter: 0, touched: Date.now(), link: link};

  function hash() { var s = ''; while (s.length < 12) s += Math.random().toString(36).slice(2); return s.slice(0, 12); }

  function forget(S) {           // local only: the server side is already gone
    try { link.removeSession(S.sid); } catch (e) {}
    S.gone = true;
  }
  function drop(S) {             // tell the server, then forget
    if (!S.gone && S.opened && link.connected()) { try { link.chartDeleteSession(S.sid); } catch (e) {} }
    forget(S);
  }
  F.destroy = function (why) {
    F.dead = true; F.why = why || F.why || 'destroyed';
    for (var key in F.series) drop(F.series[key]);
    F.series = {};
    if (window.__companionFeed === F) { try { delete window.__companionFeed; } catch (e) { window.__companionFeed = undefined; } }
  };
  function lost(why) {           // the page's connection dropped
    F.dead = true; F.why = why;
    for (var key in F.series) forget(F.series[key]);
    F.series = {};
  }

  function onSeries(S, m) {
    if (S.gone) return;
    if (Date.now() - F.touched > IDLE_MS) { F.destroy('idle'); return; }
    var p = m.params;
    switch (m.method) {
      case 'symbol_resolved':
        if (p[0] !== S.symId || S.created) return;
        var i = p[1] || {};
        S.info = {name: i.name, full_name: i.full_name, pro_name: i.pro_name, description: i.description, session: i.session,
                  timezone: i.timezone, delay: i.delay, update_mode: i.update_mode, type: i.type, subsession_id: i.subsession_id,
                  has_intraday: i.has_intraday, minmov: i.minmov, pricescale: i.pricescale};
        S.created = true; S.state = 'loading';
        link.createSeries(S.sid, S.id, S.turn, S.symId, S.resolution, S.count, null, S.handler);
        return;
      case 'symbol_error':
        if (p[0] !== S.symId) return;
        S.state = 'error'; S.error = {kind: 'symbol', text: p.slice(1).map(String).join(' ')};
        return;
      case 'series_error':
        S.state = 'error';
        var err = p[2]; var text = typeof err === 'string' ? err : (err && err.error) || JSON.stringify(err);
        S.error = {kind: 'series', text: String(text)};
        return;
      case 'series_loading':
        S.busy = true; return;
      case 'clear_data':
        S.bars = {}; S.size = 0; return;
      case 'data_update':
        var plots = (p && p.plots) || [];
        for (var k = 0; k < plots.length; k++) {
          var v = plots[k].value;
          if (!v || v.length < 5) continue;
          if (!(v[0] in S.bars)) S.size++;
          S.bars[v[0]] = [v[0], v[1], v[2], v[3], v[4], v[5] || 0];
          if (S.first === null || v[0] < S.first) S.first = v[0];
          if (S.last === null || v[0] > S.last) S.last = v[0];
        }
        if (p && p.lastBar && p.lastBar.closeTime) S.lastClose = p.lastBar.closeTime;
        S.updates++; S.updated = Date.now();
        return;
      case 'series_completed':
        S.busy = false; S.state = 'ready'; S.mode = String(p[1] || ''); S.completed++;
        if (S.more !== null) {
          if (S.size <= S.more.size) S.dry++; else S.dry = 0;
          S.more = null;
        }
        return;
    }
  }

  F.open = function (key, symbol, resolution, count) {
    F.touched = Date.now();
    if (F.dead) return {ok: false, error: 'dead', why: F.why};
    var S = F.series[key];
    if (S && S.state !== 'error') return F.status(key);
    if (S) { drop(S); delete F.series[key]; }
    var n = ++F.counter;
    S = F.series[key] = {key: key, sid: 'cs_' + hash(), id: 'sds_' + n, symId: 'sds_sym_' + n, turn: 's' + n, symbol: symbol,
                         resolution: resolution, count: count, state: 'resolving', bars: {}, size: 0, first: null, last: null,
                         info: null, error: null, mode: '', more: null, dry: 0, busy: false, completed: 0, updates: 0,
                         updated: 0, lastClose: null, opened: false, created: false, gone: false, born: Date.now(), used: Date.now()};
    S.handler = function (m) { try { onSeries(S, m); } catch (e) { S.state = 'error'; S.error = {kind: 'script', text: String((e && e.message) || e)}; } };
    var session = {onMessage: function (e) {
      if (S.gone) return;
      if (e.method === 'connected') {
        if (S.opened) { lost('reconnected'); return; }
        S.opened = true;
        link.chartCreateSession(S.sid, '');
        link.resolveSymbol(S.sid, S.symId, S.symbol, S.handler);
      } else if (e.method === 'disconnected') { lost('disconnected'); }
      else if (e.method === 'critical_error') { S.state = 'error'; S.error = {kind: 'critical', text: (e.params || []).map(String).join(' | ')}; }
    }};
    link.createSession(S.sid, session);
    return F.status(key);
  };

  F.status = function (key) {
    F.touched = Date.now();
    var out = {ok: !F.dead, dead: F.dead, why: F.why, now: Date.now(), keys: Object.keys(F.series)};
    try { out.server_time = link.serverTime(); out.connected = !!link.connected(); } catch (e) {}
    var S = F.series[key];
    if (!S) { out.state = 'none'; return out; }
    S.used = Date.now();
    out.state = S.state; out.size = S.size; out.first = S.first; out.last = S.last; out.error = S.error; out.info = S.info;
    out.mode = S.mode; out.busy = S.busy; out.more = S.more !== null; out.dry = S.dry; out.completed = S.completed;
    out.updates = S.updates; out.updated = S.updated; out.last_close = S.lastClose; out.age = Date.now() - S.born;
    return out;
  };

  F.more = function (key, bars) {
    F.touched = Date.now();
    var S = F.series[key];
    if (F.dead || !S || S.state !== 'ready' || S.busy || S.more !== null) return {asked: false};
    S.more = {size: S.size, at: Date.now()};
    link.requestMoreData(S.sid, S.id, bars, S.handler);
    return {asked: true};
  };

  F.read = function (key, count) {
    var out = F.status(key);
    var S = F.series[key];
    if (!S) return out;
    var times = Object.keys(S.bars).map(Number).sort(function (a, b) { return a - b; });
    var rows = [];
    for (var i = Math.max(0, times.length - count); i < times.length; i++) rows.push(S.bars[times[i]]);
    out.rows = rows;
    return out;
  };

  // The newest two bars of one series (the forming one last), for the companion's watcher,
  // which asks about twice a second. Reads only; opens nothing; no sort of the whole series.
  F.peek = function (key) {
    F.touched = Date.now();
    var out = {ok: !F.dead, dead: F.dead, why: F.why, now: Date.now()};
    try { out.server_time = link.serverTime(); out.connected = !!link.connected(); } catch (e) {}
    var S = F.series[key];
    if (!S) { out.state = 'none'; return out; }
    out.state = S.state; out.updated = S.updated; out.updates = S.updates; out.last_close = S.lastClose;
    var newest = null, before = null;
    for (var t in S.bars) {
      var n = Number(t);
      if (newest === null || n > newest) { before = newest; newest = n; }
      else if (n < newest && (before === null || n > before)) { before = n; }
    }
    out.rows = [];
    if (before !== null) out.rows.push(S.bars[before]);
    if (newest !== null) out.rows.push(S.bars[newest]);
    return out;
  };

  F.close = function (key) {
    var S = F.series[key];
    if (S) { drop(S); delete F.series[key]; }
    return {keys: Object.keys(F.series)};
  };

  F.list = function () {
    var out = [];
    for (var key in F.series) { var S = F.series[key]; out.push({key: key, state: S.state, size: S.size, used: S.used, updated: S.updated}); }
    return out;
  };

  window.__companionFeed = F;
  return {ok: true, reused: false, series: 0};
})(%d, %d)
""" % (VERSION, IDLE_MINUTES * 60 * 1000)

# Removes the feed and its sessions from a page. Safe when there is none.
JS_REMOVE = "(function () { var f = window.__companionFeed; if (!f) return false; f.destroy('closed'); return true; })()"


def call(method: str, *args: object) -> str:
    """The expression that calls one method of the installed feed (``{"ok": false}`` when it is gone)."""
    packed = ", ".join(json.dumps(arg) for arg in args)
    return f"(function () {{ var f = window.__companionFeed; if (!f) return {{ok: false, dead: true, why: 'missing'}}; return f.{method}({packed}); }})()"


def symbol_string(ticker: str, *, settlement_as_close: bool = False, session: str = "extended") -> str:
    """The symbol as a TradingView chart asks for it (what ``mainSeries().getSymbolString()`` shows)."""
    body: dict[str, object] = {"adjustment": "splits", "settlement-as-close": bool(settlement_as_close), "symbol": ticker}
    if session:
        body["session"] = session
    return "=" + json.dumps(body, sort_keys=True, separators=(",", ":"))
