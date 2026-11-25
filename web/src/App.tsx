import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { api, ApiError, MOCK } from "./api";
import type { ClassInfo, ClassSchema, ComputeResult, FormState, Profile } from "./types";
import { buildInputs, defaultsFromSchema, initialState, normalizeState, splitErrors, switchContentType } from "./lib/schemaForm";
import { useAfterDelay, useDebounced } from "./hooks";
import { friendlyError } from "./lib/liveRequest";
import { loadDraft, saveDraft, STORAGE_FAIL_MESSAGE } from "./lib/draft";
import { panelId, tabForKey, tabId, tabsNotAvailable, TABS, type Tab } from "./lib/tabs";
import { defaultClassId } from "./lib/classes";
import { InputsForm } from "./components/InputsForm";
import { Results } from "./components/Results";
import { ProfilesPanel } from "./components/ProfilesPanel";
import { ClassPicker } from "./components/ClassPicker";
import { StatValues } from "./components/StatValues";
import { ArtifactsPanel } from "./components/ArtifactsPanel";
import { CubesPanel } from "./components/CubesPanel";
import { EquipmentPanel } from "./components/EquipmentPanel";
import { CompanionsPanel } from "./components/CompanionsPanel";
import { HelpPanel } from "./components/HelpPanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { useCubesMeta } from "./lib/useLive";
import { CLOUD_ENABLED } from "./lib/cloud/config";
import { noteLastProfile } from "./lib/cloud/bridge";
import { COMPANION_SECTION_ID, EQUIPPED_SECTION_ID, artifactStarsExtra, artifactsAvailable } from "./lib/artifacts";

// Accounts (Google sign-in + cloud-saved profiles): only when the VITE_FIREBASE_* variables are set; a separate lazy chunk, and the Firebase SDK is a further chunk
const AccountRoot = CLOUD_ENABLED ? lazy(() => import("./components/account/AccountRoot")) : null;

/** One tabpanel of the tab bar (always in the DOM so the tabs' aria-controls resolve; the content decides itself whether it stays mounted while hidden). */
function Panel({ id, active, children }: { id: Tab; active: boolean; children?: ReactNode }) {
  return (
    <div role="tabpanel" id={panelId(id)} aria-labelledby={tabId(id)} hidden={!active}>
      {children}
    </div>
  );
}

const smooth = (): ScrollBehavior => (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

export default function App() {
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [classId, setClassId] = useState<string | null>(null);
  const [schema, setSchema] = useState<ClassSchema | null>(null);
  const [state, setState] = useState<FormState | null>(null);
  const [result, setResult] = useState<ComputeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [fatal, setFatal] = useState<string | null>(null); // can't reach API / schema load failure
  const [computeError, setComputeError] = useState<string | null>(null);
  const [computeUnreachable, setComputeUnreachable] = useState(false); // the compute request never got an answer: offer Retry
  const [retryNonce, setRetryNonce] = useState(0);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [tab, setTab] = useState<Tab>("calc");
  const [storageFailed, setStorageFailed] = useState(false);
  const loadSeq = useRef(0);
  // cube tabs (Cubes, Equipment compare, the Artifacts tab's potential lines): static tables fetched once per class, only once one of them is opened
  const classInfo = classes.find((c) => c.id === classId);
  const cubesSupported = classInfo?.status?.stat_values;
  const [cubesWanted, setCubesWanted] = useState(false);
  const { meta: cubesMeta, status: cubesMetaStatus } = useCubesMeta(classId, cubesWanted && cubesSupported !== false);
  useEffect(() => {
    if (tab === "cubes" || tab === "equip" || tab === "artifacts") setCubesWanted(true);
  }, [tab]);
  const scrollTarget = useRef<string | null>(null); // section id of the Calculator tab to scroll to once it is shown

  const selectClass = useCallback(async (id: string, restore?: FormState) => {
    const seq = ++loadSeq.current;
    setFatal(null);
    setResult(null);
    setFieldErrors({});
    try {
      const sch = await api.schema(id);
      const ct = restore?.contentType ?? sch.content_types[0];
      const defs = await api.defaults(id, ct);
      if (seq !== loadSeq.current) return;
      setSchema(sch);
      setClassId(id);
      setState(restore ? normalizeState(sch, restore) : initialState(sch, defs, ct));
    } catch (e) {
      if (seq === loadSeq.current) setFatal(friendlyError(e, "calculator"));
    }
  }, []);

  const loadClasses = useCallback(() => {
    setFatal(null);
    api
      .classes()
      .then((list) => {
        setClasses(list);
        // the draft autosave (lib/draft.ts) brings back the inputs of the last visit; a class that is gone is ignored
        const draft = loadDraft();
        if (draft && list.some((c) => c.id === draft.classId)) void selectClass(draft.classId, draft);
        else {
          const first = defaultClassId(list);
          if (first) void selectClass(first);
          else setFatal("The calculator server reports no classes.");
        }
      })
      .catch((e) => setFatal(friendlyError(e, "calculator")));
  }, [selectClass]);

  useEffect(() => {
    loadClasses();
  }, [loadClasses]);

  // Retry of the "can't reach the server" banner: reload the class list, or just the class when the list is already there
  const retryLoad = () => (classes.length && classId ? void selectClass(classId) : loadClasses());

  const loadDefaults = useCallback(
    async (ct: string) => {
      if (!schema || !classId) return;
      let defs;
      try {
        defs = await api.defaults(classId, ct);
      } catch {
        defs = defaultsFromSchema(schema, ct); // offline fallback: the schema carries the same defaults
      }
      setState((s) => (s ? switchContentType(s, schema, ct, defs) : s));
    },
    [schema, classId],
  );

  // silent draft autosave: whatever is typed is kept in this browser; the only text is the one-line message when the browser refuses
  const debouncedState = useDebounced(state, 800);
  useEffect(() => {
    if (debouncedState) setStorageFailed(!saveDraft(debouncedState));
  }, [debouncedState]);

  // debounced auto-compute
  const inputs = useMemo(() => (schema && state ? buildInputs(schema, state) : null), [schema, state]);
  // Stat values (the equip ranking part) also get the star of EVERY artifact from the Artifacts table, not only of the equipped ones
  const statInputs = useMemo(() => (inputs && schema?.artifacts_modelled && schema.artifacts ? { ...inputs, ...artifactStarsExtra(schema.artifacts, state?.artifacts) } : inputs), [inputs, schema, state?.artifacts]);
  const inputsKey = inputs ? JSON.stringify(inputs) : "";
  const debouncedKey = useDebounced(inputsKey, 350);
  const stale = inputsKey !== debouncedKey;

  useEffect(() => {
    if (!debouncedKey || !classId || !schema) return;
    const ctl = new AbortController();
    setBusy(true);
    api
      .compute(classId, JSON.parse(debouncedKey), ctl.signal)
      .then((r) => {
        setResult(r);
        setComputeError(null);
        setComputeUnreachable(false);
        setFieldErrors({});
      })
      .catch((e: unknown) => {
        if ((e as Error).name === "AbortError") return;
        if (e instanceof ApiError && e.status === 422) {
          const { byField, general } = splitErrors(e.fieldErrors, schema);
          setFieldErrors(byField);
          setComputeUnreachable(false);
          setComputeError(general.length ? general.join("; ") : "Some inputs are invalid - see the highlighted fields.");
        } else {
          setComputeUnreachable(e instanceof ApiError && e.status === 0);
          setComputeError(friendlyError(e, "calculation"));
        }
      })
      .finally(() => {
        if (!ctl.signal.aborted) setBusy(false);
      });
    return () => ctl.abort();
  }, [debouncedKey, classId, schema, retryNonce]);

  // a free-tier server that has been idle needs a moment to start: say so only when it really takes a while
  const slowLoad = useAfterDelay(!schema && !fatal, 3000);
  const slowCompute = useAfterDelay(busy && !result, 3000);
  const WAKING = "Waking up the free server (up to ~20 s)...";

  // Artifacts tab -> "go to Companion" / "go to Equipped artifacts": switch to the calculator, then scroll to that section once it is rendered
  const openCalcSection = (id: string) => {
    scrollTarget.current = id;
    setTab("calc");
  };
  const openCompanion = () => openCalcSection(COMPANION_SECTION_ID);
  const openEquipped = () => openCalcSection(EQUIPPED_SECTION_ID);
  useEffect(() => {
    if (tab === "calc" && scrollTarget.current && schema && state) {
      const id = scrollTarget.current;
      scrollTarget.current = null;
      document.getElementById(id)?.scrollIntoView?.({ behavior: smooth(), block: "start" });
    }
  }, [tab, schema, state]);

  // account dialogs link to a Help section
  const helpAnchor = useRef<string | null>(null);
  const openHelp = (id: string) => {
    helpAnchor.current = id;
    setTab("help");
  };
  // the address .../#privacy opens the privacy policy (a stable link for the sign-in consent screen / footer)
  useEffect(() => {
    if (window.location.hash === "#privacy") openHelp("help-privacy");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (tab === "help" && helpAnchor.current) {
      const id = helpAnchor.current;
      helpAnchor.current = null;
      document.getElementById(id)?.scrollIntoView?.({ behavior: smooth(), block: "start" });
    }
  }, [tab]);

  const loadProfile = (p: Profile) => {
    noteLastProfile(p.id);
    setTab("calc");
    if (p.state.classId === classId && schema) setState(normalizeState(schema, p.state));
    else void selectClass(p.state.classId, p.state);
  };

  // a tab says "soon" when the class does not have what it needs yet (the tab itself explains and links to Help)
  const soonTabs = tabsNotAvailable(classInfo?.status, !schema || artifactsAvailable(schema, classInfo));
  const tabUnavailable = (t: Tab) => soonTabs.includes(t);
  const onTabKey = (e: KeyboardEvent, current: Tab) => {
    const next = tabForKey(current, e.key);
    if (!next) return;
    e.preventDefault();
    setTab(next);
    document.getElementById(tabId(next))?.focus();
  };

  return (
    <div className="app">
      <header>
        <h1>MapleStory Idle DPS</h1>
        {MOCK && <span className="pill off" title="VITE_MOCK=1: fixture data, no API calls">mock data</span>}
        <div className="spacer" />
        <ClassPicker classes={classes} value={classId} onChange={(id) => void selectClass(id)} />
        <ThemeToggle />
        {AccountRoot && (
          <Suspense fallback={null}>
            <AccountRoot classId={classId} classes={classes} onApplyClass={(id) => void selectClass(id)} onOpenHelp={openHelp} />
          </Suspense>
        )}
      </header>

      <nav className="tabs" role="tablist" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={tabId(t.id)}
            aria-selected={tab === t.id}
            aria-controls={panelId(t.id)}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => setTab(t.id)}
            onKeyDown={(e) => onTabKey(e, t.id)}
          >
            {t.label}
            {tabUnavailable(t.id) && (
              <span className="tab-soon" title="Not available for this class yet">
                soon
              </span>
            )}
          </button>
        ))}
      </nav>

      <main>
        {fatal && (
          <div className="banner error" role="alert">
            {fatal}{" "}
            <button type="button" onClick={retryLoad}>
              Retry
            </button>
          </div>
        )}
        {storageFailed && (
          <p className="notice" role="status">
            {STORAGE_FAIL_MESSAGE}
          </p>
        )}

        <Panel id="calc" active={tab === "calc"}>
          {schema && state && tab === "calc" && (
            <>
              <div className="layout">
                <div className="col-form">
                  <InputsForm
                    schema={schema}
                    state={state}
                    onState={setState}
                    errors={fieldErrors}
                    derived={result?.derived}
                    loadDefaults={(ct) => void loadDefaults(ct)}
                    onOpenCompanions={() => setTab("companions")}
                    classInfo={classInfo}
                    onOpenArtifacts={() => setTab("artifacts")}
                  />
                </div>
                <div className="col-results">
                  {computeError && (
                    <div className="banner error" role="alert">
                      {computeError}
                      {computeUnreachable && (
                        <>
                          {" "}
                          <button type="button" onClick={() => setRetryNonce((n) => n + 1)}>
                            Retry
                          </button>
                        </>
                      )}
                      {Object.keys(fieldErrors).length > 0 && (
                        <ul>
                          {Object.entries(fieldErrors).map(([k, m]) => (
                            <li key={k}>
                              <strong>{schema.fields.find((f) => f.key === k)?.label ?? k}</strong>: {m}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                  {result ? <Results result={result} busy={busy} stale={stale} /> : <p className="empty">{busy ? (slowCompute ? WAKING : "Calculating...") : "Enter inputs to see results."}</p>}
                </div>
              </div>
              <AboutNumbers onOpenLimitations={() => openHelp("help-limitations")} />
            </>
          )}
        </Panel>

        {/* the Companions tab stays mounted like Stat values (its tables survive a tab switch); it only requests while visible */}
        <Panel id="companions" active={tab === "companions"}>
          {schema && state && (
            <CompanionsPanel
              onOpenHelp={() => openHelp("help-modelled")}
              classId={classId}
              schema={schema}
              state={state}
              onState={setState}
              inputs={inputs}
              active={tab === "companions"}
              supported={classInfo?.status?.stat_values}
              onOpenCalculator={() => setTab("calc")}
            />
          )}
        </Panel>

        <Panel id="artifacts" active={tab === "artifacts"}>
          {schema && state && tab === "artifacts" && (
            <ArtifactsPanel
              onOpenHelp={() => openHelp("help-modelled")}
              schema={schema}
              classInfo={classes.find((c) => c.id === classId)}
              state={state}
              onState={setState}
              result={result}
              busy={busy}
              stale={stale}
              onOpenCompanion={openCompanion}
              onOpenInputs={openEquipped}
              cubesMeta={cubesSupported === false ? undefined : cubesMeta}
              cubesMetaStatus={cubesMetaStatus}
            />
          )}
        </Panel>

        {/* stays mounted once the class is loaded (so the tables survive a tab switch); it only requests while visible */}
        <Panel id="stats" active={tab === "stats"}>
          {schema && state && (
            <StatValues
              onOpenHelp={() => openHelp("help-modelled")}
              classId={classId}
              inputs={statInputs}
              active={tab === "stats"}
              supported={classes.find((c) => c.id === classId)?.status?.stat_values}
            />
          )}
        </Panel>

        {/* the two cube tabs stay mounted (a Calculate result survives a tab switch); they only request while visible */}
        <Panel id="cubes" active={tab === "cubes"}>
          {schema && state && (
            <CubesPanel
              onOpenHelp={() => openHelp("help-modelled")}
              classId={classId}
              inputs={inputs}
              supported={cubesSupported}
              active={tab === "cubes"}
              meta={cubesMeta}
              metaStatus={cubesMetaStatus}
              state={state.cubes}
              onState={(cubes) => setState((s) => (s ? { ...s, cubes } : s))}
            />
          )}
        </Panel>
        <Panel id="equip" active={tab === "equip"}>
          {schema && state && (
            <EquipmentPanel
              onOpenHelp={() => openHelp("help-modelled")}
              classId={classId}
              inputs={inputs}
              supported={cubesSupported}
              active={tab === "equip"}
              meta={cubesMeta}
              metaStatus={cubesMetaStatus}
              state={state.equipment}
              onState={(equipment) => setState((s) => (s ? { ...s, equipment } : s))}
            />
          )}
        </Panel>

        <Panel id="profiles" active={tab === "profiles"}>
          {schema && state && tab === "profiles" && <ProfilesPanel state={state} classes={classes} onLoad={loadProfile} />}
        </Panel>

        <Panel id="help" active={tab === "help"}>
          {tab === "help" && <HelpPanel classes={classes} schema={schema} />}
        </Panel>

        {!schema && !fatal && tab !== "help" && <p className="empty">{slowLoad ? WAKING : "Loading..."}</p>}
      </main>
      <footer className="site-footer">
        <a
          href="#privacy"
          onClick={(e) => {
            e.preventDefault();
            window.history.replaceState(null, "", "#privacy");
            openHelp("help-privacy");
          }}
        >
          Privacy policy
        </a>
        <span> · Fan-made, not affiliated with Nexon</span>
      </footer>
    </div>
  );
}

/** The one explanation block of the Calculator tab: collapsed, at the bottom (nothing explanatory sits above the controls or the results). */
export function AboutNumbers({ onOpenLimitations }: { onOpenLimitations?: () => void }) {
  return (
    <details className="card about">
      <summary>About these numbers</summary>
      <ul>
        <li>Type the values shown on your preset page in game. The calculator applies buffs, companions and artifacts itself.</li>
        <li>The result is an estimate: differences of 1-2% are noise.</li>
        <li>Numbers can be typed as 12.5M. Units: K = thousand, M = million, B = billion, T = trillion, Qa = 10^15, Qi = 10^18, Sx = 10^21, Sp = 10^24.</li>
        <li>Hover or tap a number to see the full figure.</li>
        <li>
          What is and is not modelled:{" "}
          <button type="button" className="link" onClick={onOpenLimitations} disabled={!onOpenLimitations}>
            Help: Known limitations
          </button>
          .
        </li>
      </ul>
    </details>
  );
}
