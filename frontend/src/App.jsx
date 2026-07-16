import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { fetchCatalog, fetchCatalogList, fetchHealth, solveSchedule } from "./api.js";

const SEASON_OPTIONS = ["Fall", "Spring", "Summer"];

function StatBadge({ label, value, tone }) {
  return (
    <div className={`stat-badge tone-${tone || "neutral"}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}

function ControlPanel({ catalogList, catalogId, setCatalogId, catalog, profile, setProfile, onRun, running, health }) {
  const categories = useMemo(() => {
    if (!catalog) return {};
    const groups = {};
    Object.values(catalog.courses).forEach((c) => {
      const key = c.categories[0] || "other";
      groups[key] = groups[key] || [];
      groups[key].push(c);
    });
    return groups;
  }, [catalog]);

  const toggleCompleted = (code) => {
    setProfile((p) => {
      const set = new Set(p.completed_codes);
      set.has(code) ? set.delete(code) : set.add(code);
      return { ...p, completed_codes: Array.from(set) };
    });
  };

  return (
    <aside className="control-panel">
      <div className="brand">
        <span className="brand-mark">✈</span>
        <div>
          <h1>Flightpath</h1>
          <p className="brand-sub">Degree route planner</p>
        </div>
      </div>

      <div className="panel-section">
        <div className="section-head">
          <span>Program</span>
        </div>
        <select
          className="program-select"
          value={catalogId || ""}
          onChange={(e) => setCatalogId(e.target.value)}
        >
          {catalogList.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        {catalog && (
          <p className="program-desc">{catalogList.find((c) => c.id === catalogId)?.description}</p>
        )}
      </div>

      <div className="panel-section">
        <div className="section-head">
          <span>Solver backend</span>
        </div>
        <div className={`solver-readout ${health?.solver_backend?.includes("optimal") ? "optimal" : "fallback"}`}>
          {health ? health.solver_backend : "checking…"}
        </div>
      </div>

      <div className="panel-section">
        <div className="section-head">
          <span>Flight parameters</span>
        </div>
        <label className="field">
          <span>Max credits / term</span>
          <input
            type="range"
            min={9}
            max={21}
            value={profile.max_credits_per_term}
            onChange={(e) => setProfile((p) => ({ ...p, max_credits_per_term: Number(e.target.value) }))}
          />
          <span className="field-readout mono">{profile.max_credits_per_term}</span>
        </label>

        <label className="field">
          <span>Starting term</span>
          <select
            value={profile.starting_season}
            onChange={(e) => setProfile((p) => ({ ...p, starting_season: e.target.value }))}
          >
            {SEASON_OPTIONS.filter((s) => s !== "Summer").map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>

        <label className="field field-toggle">
          <span>Include summer terms</span>
          <input
            type="checkbox"
            checked={profile.include_summers}
            onChange={(e) => setProfile((p) => ({ ...p, include_summers: e.target.checked }))}
          />
        </label>

        <label className="field field-toggle">
          <span>Avoid early-morning courses</span>
          <input
            type="checkbox"
            checked={profile.avoid_early_morning}
            onChange={(e) => setProfile((p) => ({ ...p, avoid_early_morning: e.target.checked }))}
          />
        </label>
      </div>

      <div className="panel-section grow">
        <div className="section-head">
          <span>Already completed</span>
          <span className="section-count mono">{profile.completed_codes.length}</span>
        </div>
        <div className="completed-list">
          {Object.entries(categories).map(([cat, courses]) => (
            <div key={cat} className="cat-group">
              <div className="cat-label">{cat.replace(/_/g, " ")}</div>
              {courses.map((c) => (
                <label key={c.code} className="course-check">
                  <input
                    type="checkbox"
                    checked={profile.completed_codes.includes(c.code)}
                    onChange={() => toggleCompleted(c.code)}
                  />
                  <span className="mono code">{c.code}</span>
                  <span className="course-title">{c.title}</span>
                </label>
              ))}
            </div>
          ))}
        </div>
      </div>

      <button className="run-btn" onClick={onRun} disabled={running}>
        {running ? "Plotting route…" : "Plot optimal route"}
      </button>
    </aside>
  );
}

function CourseChip({ course, code, onRef, critical, earlyFlag }) {
  return (
    <div
      ref={(el) => onRef(code, el)}
      className={`course-chip ${critical ? "critical" : ""} ${earlyFlag ? "early" : ""}`}
    >
      <div className="chip-top">
        <span className="mono chip-code">{code}</span>
        <span className="mono chip-credits">{course.credits}cr</span>
      </div>
      <div className="chip-title">{course.title}</div>
      <div className="chip-bottom">
        <span className="chip-rating">{"★".repeat(Math.round(course.rating))}<span className="dim">{"★".repeat(5 - Math.round(course.rating))}</span></span>
        {earlyFlag && <span className="chip-flag">early</span>}
      </div>
    </div>
  );
}

function RouteBoard({ catalog, result }) {
  const boardRef = useRef(null);
  const chipRefs = useRef(new Map());
  const [lines, setLines] = useState([]);

  const registerRef = (code, el) => {
    if (el) chipRefs.current.set(code, el);
    else chipRefs.current.delete(code);
  };

  const termGroups = useMemo(() => {
    if (!result?.feasible) return [];
    const groups = result.term_labels.map(() => []);
    Object.entries(result.assignment).forEach(([code, t]) => {
      groups[t].push(code);
    });
    return groups.map((codes) =>
      codes.sort((a, b) => catalog.courses[b].credits - catalog.courses[a].credits)
    );
  }, [result, catalog]);

  const criticalSet = useMemo(() => {
    // Longest prereq chain among scheduled courses -- the courses that
    // actually determine how many terms the plan needs.
    if (!result?.feasible) return new Set();
    const depth = {};
    const codes = Object.keys(result.assignment);
    const byCode = catalog.courses;
    const memo = {};
    function longest(code) {
      if (memo[code] !== undefined) return memo[code];
      const prereqs = (byCode[code].prereqs || []).filter((p) => result.assignment[p] !== undefined);
      const val = prereqs.length ? 1 + Math.max(...prereqs.map(longest)) : 1;
      memo[code] = val;
      return val;
    }
    codes.forEach((c) => (depth[c] = longest(c)));
    const max = Math.max(0, ...Object.values(depth));
    // Walk back one path achieving max depth.
    const critical = new Set();
    let frontier = codes.filter((c) => depth[c] === max);
    while (frontier.length) {
      const c = frontier.pop();
      if (critical.has(c)) continue;
      critical.add(c);
      const prereqs = (byCode[c].prereqs || []).filter((p) => result.assignment[p] !== undefined);
      const next = prereqs.find((p) => depth[p] === depth[c] - 1);
      if (next) frontier.push(next);
    }
    return critical;
  }, [result, catalog]);

  useLayoutEffect(() => {
    if (!result?.feasible || !boardRef.current) {
      setLines([]);
      return;
    }
    const boardRect = boardRef.current.getBoundingClientRect();
    const newLines = [];
    Object.entries(result.assignment).forEach(([code, term]) => {
      const course = catalog.courses[code];
      (course.prereqs || []).forEach((p) => {
        if (result.assignment[p] === undefined) return;
        const fromEl = chipRefs.current.get(p);
        const toEl = chipRefs.current.get(code);
        if (!fromEl || !toEl) return;
        const fromRect = fromEl.getBoundingClientRect();
        const toRect = toEl.getBoundingClientRect();
        const x1 = fromRect.right - boardRect.left;
        const y1 = fromRect.top + fromRect.height / 2 - boardRect.top;
        const x2 = toRect.left - boardRect.left;
        const y2 = toRect.top + toRect.height / 2 - boardRect.top;
        const isCritical = criticalSet.has(code) && criticalSet.has(p);
        newLines.push({ x1, y1, x2, y2, key: `${p}->${code}`, critical: isCritical });
      });
    });
    setLines(newLines);
  }, [result, catalog, criticalSet]);

  if (!result) {
    return (
      <div className="empty-board">
        <div className="empty-glyph">✈</div>
        <p>Set your flight parameters and plot a route to see your term-by-term plan.</p>
      </div>
    );
  }

  if (!result.feasible) {
    return (
      <div className="empty-board infeasible">
        <div className="empty-glyph">⚠</div>
        <p>{result.reason || "No feasible route found."}</p>
        {result.conflicts?.length > 0 && (
          <ul className="conflict-list">
            {result.conflicts.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="route-board" ref={boardRef}>
      <svg className="connector-layer">
        {lines.map((l) => (
          <path
            key={l.key}
            d={`M ${l.x1} ${l.y1} C ${l.x1 + 40} ${l.y1}, ${l.x2 - 40} ${l.y2}, ${l.x2} ${l.y2}`}
            className={l.critical ? "connector critical" : "connector"}
          />
        ))}
      </svg>
      {result.term_labels.map((label, t) => (
        <div className="term-column" key={label}>
          <div className="term-head">
            <span className="term-label">{label}</span>
            <span className="term-credits mono">{result.total_credits[t]}cr</span>
          </div>
          <div className="term-stack">
            {termGroups[t].map((code) => (
              <CourseChip
                key={code}
                code={code}
                course={catalog.courses[code]}
                onRef={registerRef}
                critical={criticalSet.has(code)}
                earlyFlag={catalog.courses[code].is_early_morning}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [catalogList, setCatalogList] = useState([]);
  const [catalogId, setCatalogId] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [health, setHealth] = useState(null);
  const [profile, setProfile] = useState({
    completed_codes: [],
    max_credits_per_term: 16,
    min_credits_per_term: 12,
    avoid_early_morning: false,
    starting_season: "Fall",
    include_summers: false,
    max_terms_horizon: 10,
  });
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCatalogList()
      .then((data) => {
        setCatalogList(data.catalogs);
        if (data.catalogs.length > 0) setCatalogId(data.catalogs[0].id);
      })
      .catch((e) => setError(e.message));
    fetchHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (!catalogId) return;
    setCatalog(null);
    setResult(null);
    setProfile((p) => ({ ...p, completed_codes: [] }));
    fetchCatalog(catalogId).then(setCatalog).catch((e) => setError(e.message));
  }, [catalogId]);

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await solveSchedule({ ...profile, catalog_id: catalogId });
      setResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="app-shell">
      {catalog ? (
        <ControlPanel
          catalogList={catalogList}
          catalogId={catalogId}
          setCatalogId={setCatalogId}
          catalog={catalog}
          profile={profile}
          setProfile={setProfile}
          onRun={run}
          running={running}
          health={health}
        />
      ) : (
        <aside className="control-panel loading">Loading catalog…</aside>
      )}

      <main className="main-view">
        {result?.feasible && (
          <div className="status-row">
            <StatBadge label="Terms to graduate" value={result.terms_used} tone="amber" />
            <StatBadge label="Avg course rating" value={result.avg_rating.toFixed(2)} tone="teal" />
            <StatBadge label="Solver" value={result.solver_used.includes("cp-sat") ? "CP-SAT (optimal)" : "Heuristic fallback"} tone={result.solver_used.includes("cp-sat") ? "teal" : "amber"} />
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}
        <RouteBoard catalog={catalog} result={result} />
      </main>
    </div>
  );
}
