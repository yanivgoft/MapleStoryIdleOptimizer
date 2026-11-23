import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, MOCK } from "./api";
import type { ClassInfo, ClassSchema, ComputeResult, FormState, Profile } from "./types";
import { buildInputs, defaultsFromSchema, initialState, normalizeState, splitErrors, switchContentType } from "./lib/schemaForm";
import { useDebounced } from "./hooks";
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
import { COMPANION_SECTION_ID, EQUIPPED_SECTION_ID, artifactStarsExtra } from "./lib/artifacts";

// Accounts (Google sign-in + cloud-saved profiles): only when the VITE_FIREBASE_* variables are set; a separate lazy chunk, and the Firebase SDK is a further chunk
const AccountRoot = CLOUD_ENABLED ? lazy(() => import("./components/account/AccountRoot")) : null;

type Tab = "calc" | "companions" | "profiles" | "artifacts" | "stats" | "cubes" | "equip" | "help";

export default function App() {
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [classId, setClassId] = useState<string | null>(null);
  const [schema, setSchema] = useState<ClassSchema | null>(null);
  const [state, setState] = useState<FormState | null>(null);
  const [result, setResult] = useState<ComputeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [fatal, setFatal] = useState<string | null>(null); // can't reach API / schema load failure
  const [computeError, setComputeError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [tab, setTab] = useState<Tab>("calc");
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
      if (seq === loadSeq.current) setFatal((e as Error).message);
    }
  }, []);

  useEffect(() => {
    api
      .classes()
      .then((list) => {
        setClasses(list);
        const first = defaultClassId(list);
        if (first) void selectClass(first);
        else setFatal("The API reports no classes.");
      })
      .catch((e) => setFatal((e as Error).message));
  }, [selectClass]);

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
        setFieldErrors({});
      })
      .catch((e: unknown) => {
        if ((e as Error).name === "AbortError") return;
        if (e instanceof ApiError && e.status === 422) {
          const { byField, general } = splitErrors(e.fieldErrors, schema);
          setFieldErrors(byField);
          setComputeError(general.length ? general.join("; ") : "Some inputs are invalid - see the highlighted fields.");
        } else {
          setComputeError((e as Error).message);
        }
      })
      .finally(() => {
        if (!ctl.signal.aborted) setBusy(false);
      });
    return () => ctl.abort();
  }, [debouncedKey, classId, schema]);

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
      document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
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
      document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    }
  }, [tab]);

  const loadProfile = (p: Profile) => {
    noteLastProfile(p.id);
    setTab("calc");
    if (p.state.classId === classId && schema) setState(normalizeState(schema, p.state));
    else void selectClass(p.state.classId, p.state);
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
        <button role="tab" aria-selected={tab === "calc"} onClick={() => setTab("calc")}>
          Calculator
        </button>
        <button role="tab" aria-selected={tab === "companions"} onClick={() => setTab("companions")}>
          Companions
        </button>
        <button role="tab" aria-selected={tab === "profiles"} onClick={() => setTab("profiles")}>
          Profiles
        </button>
        <button role="tab" aria-selected={tab === "stats"} onClick={() => setTab("stats")}>
          Stat values
        </button>
        <button role="tab" aria-selected={tab === "artifacts"} onClick={() => setTab("artifacts")}>
          Artifacts
        </button>
        <button role="tab" aria-selected={tab === "cubes"} onClick={() => setTab("cubes")}>
          Cubes
        </button>
        <button role="tab" aria-selected={tab === "equip"} onClick={() => setTab("equip")}>
          Equipment compare
        </button>
        <button role="tab" aria-selected={tab === "help"} onClick={() => setTab("help")}>
          Help
        </button>
      </nav>

      {fatal && (
        <div className="banner error" role="alert">
          {fatal}
        </div>
      )}

      {tab === "help" && <HelpPanel classes={classes} schema={schema} />}

      {schema && state && tab === "profiles" && <ProfilesPanel state={state} classes={classes} onLoad={loadProfile} />}

      {schema && state && tab === "artifacts" && (
        <ArtifactsPanel
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

      {/* the Companions tab stays mounted like Stat values (its tables survive a tab switch); it only requests while visible */}
      {schema && state && (
        <div hidden={tab !== "companions"}>
          <CompanionsPanel
            classId={classId}
            schema={schema}
            state={state}
            onState={setState}
            inputs={inputs}
            active={tab === "companions"}
            supported={classInfo?.status?.stat_values}
            onOpenCalculator={() => setTab("calc")}
          />
        </div>
      )}

      {/* the two cube tabs stay mounted (a Calculate result survives a tab switch); they only request while visible */}
      {schema && state && (
        <div hidden={tab !== "cubes"}>
          <CubesPanel
            classId={classId}
            inputs={inputs}
            supported={cubesSupported}
            active={tab === "cubes"}
            meta={cubesMeta}
            metaStatus={cubesMetaStatus}
            state={state.cubes}
            onState={(cubes) => setState((s) => (s ? { ...s, cubes } : s))}
          />
        </div>
      )}
      {schema && state && (
        <div hidden={tab !== "equip"}>
          <EquipmentPanel
            classId={classId}
            inputs={inputs}
            supported={cubesSupported}
            active={tab === "equip"}
            meta={cubesMeta}
            metaStatus={cubesMetaStatus}
            state={state.equipment}
            onState={(equipment) => setState((s) => (s ? { ...s, equipment } : s))}
          />
        </div>
      )}

      {/* stays mounted once the class is loaded (so the tables survive a tab switch); it only requests while visible */}
      {schema && state && (
        <div hidden={tab !== "stats"}>
          <StatValues
            classId={classId}
            inputs={statInputs}
            active={tab === "stats"}
            supported={classes.find((c) => c.id === classId)?.status?.stat_values}
          />
        </div>
      )}

      {schema && state && tab === "calc" && (
        <main className="layout">
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
            {result ? <Results result={result} busy={busy} stale={stale} /> : <p className="empty">{busy ? "Calculating..." : "Enter inputs to see results."}</p>}
          </div>
        </main>
      )}
      {!schema && !fatal && tab !== "help" && <p className="empty">Loading...</p>}
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
