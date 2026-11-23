// Copy of the Help tab.  Edit the text here; HelpPanel.tsx assembles it (and adds the two parts that come from data: the per-field hints of the
// selected class and the per-class "what is modelled" table).  Keep the claims in sync with APP.md / KNOWN_GAPS.md.
import type { ReactNode } from "react";
import type { ClassInfo } from "../types";

export const KNOWN_GAPS_URL = "https://github.com/yanivgoft/MapleStoryIdleOptimizer/blob/main/KNOWN_GAPS.md";

export interface HelpSection {
  id: string; // anchor, used by the table of contents
  title: string;
  body: ReactNode;
}

// ---- what each class supports (table) --------------------------------------------------------------------------------------------------------------

export const CAPABILITY_COLUMNS = ["Calculator", "Artifacts", "Companions", "Stat values", "Cubes", "Equipment compare"] as const;
export type Capability = (typeof CAPABILITY_COLUMNS)[number];

/** Per class: does each feature work?  Calculator is always on; Artifacts / Companions follow `status`; Stat values, Cubes and Equipment compare share one
 *  switch (`status.stat_values`: the cube tabs price stats with the stat-values engine). */
export function classCapabilities(c: ClassInfo): Record<Capability, boolean> {
  const st = c.status ?? {};
  const statValues = st.stat_values === true;
  return {
    Calculator: true,
    Artifacts: st.artifacts ?? c.artifacts_modelled ?? false,
    Companions: st.companions !== false,
    "Stat values": statValues,
    Cubes: statValues,
    "Equipment compare": statValues,
  };
}

// ---- sections ---------------------------------------------------------------------------------------------------------------------------------------

export const INTRO = (
  <p>
    This app estimates your damage per second (DPS) from the character stats you type in, for the 12 classes it supports, and tells you which stat, artifact, companion or potential line
    would raise it the most.  It is a model of the game, not the game itself: read the conventions and the known limitations below before trusting a small difference.
  </p>
);

export const HOW_TO_USE: HelpSection = {
  id: "help-how-to-use",
  title: "How to use it",
  body: (
    <>
      <ol>
        <li>
          <strong>Pick your class</strong> in the header.  The status line next to it says which features exist for that class.
        </li>
        <li>
          <strong>Pick a content type</strong> on the Calculator (Chapter Boss, Breakthrough, PvP, a dungeon, World Boss, Chapter Hunt).  Add the chapter / stage when it asks.  Each content type keeps its
          own stats, like the columns of the workbook, so you can type your PvP stats once and come back to them.
        </li>
        <li>
          <strong>Type your stats</strong> from the in-game stat screen (see "Which stats to type" below).  The result updates a moment after you stop typing.
        </li>
        <li>
          <strong>Read the Calculator result</strong>: Total DPS, the boss / normal-monster split, a per-skill breakdown and, when a companion is chosen, its share.
        </li>
      </ol>
      <h4>The tabs</h4>
      <ul>
        <li>
          <strong>Calculator</strong> - the inputs and the result.
        </li>
        <li>
          <strong>Companions</strong> - set the level of each companion you own (Not unlocked, 1-18).  Compares them (DPS gain vs no companion, rank) and shows what boots lines of Summoning Time are worth.  The
          companion you actually use in a content type is chosen on the Calculator.
        </li>
        <li>
          <strong>Profiles</strong> - save the current setup in your browser, load it later, export it to a JSON file and import it on another device, or import your Excel calculator's values (see "Import from Excel" below).  Stats, companion levels, artifacts and the cube / equipment
          editors are all part of a profile.
        </li>
        <li>
          <strong>Stat values</strong> - what one more point of each stat is worth for your current build (DPS gain, % gain, and "units per +1% DPS").
        </li>
        <li>
          <strong>Artifacts</strong> - one table with all 36 artifacts (like the workbook's ArtifactsInput sheet): set each artifact's star level (Not unlocked, 0-5), tick the ones you have equipped
          (<strong>5 slots</strong>: once five are ticked the other boxes are disabled until you untick one) and, per artifact, up to three potential lines (rarity + stat; the third line only for Legendary
          artifacts) with the DPS each line and the artifact's potential total would add.  Filter the table by name or show only unlocked / equipped artifacts.  Below it: what the equipped artifacts do in the
          calculation and the equip ranking.  "Not unlocked" acts as star 0 once the artifact is equipped.
        </li>
        <li>
          <strong>Cubes</strong> - enter the potential and bonus-potential lines of your 15 equipment slots (each line's stat list shows only what that piece can roll) and press Calculate: for each slot, how many cubes until rolling is expected to pay off, and whether it is
          worth rolling.
        </li>
        <li>
          <strong>Equipment compare</strong> - type the lines of the equip you wear and the one you could swap to; shows which is better and by how much.
        </li>
        <li>
          <strong>Help</strong> - this page.
        </li>
      </ul>
      <h4>Import from Excel</h4>
      <p>
        Used the Excel calculator before?  <strong>Profiles &gt; Import from Excel (.xlsx)</strong> (or drop the file on it) loads the values you typed into your own{" "}
        <code>&lt;Class&gt;-DPS-Calculator.xlsx</code>, so you do not have to retype them.  A preview shows what will be imported and any warnings; pressing Import saves it as a NEW profile (a profile with the same
        name is never overwritten).
      </p>
      <ul>
        <li>
          <strong>What is read</strong>: the class (from the title of the Inputs sheet), the character level, every value of the Inputs sheet for each content type (columns C-L, found by their headers), the
          Chapter-Stage text, Boss/Normal emphasis, max enemies, PvP fight length, the companion chosen per content type and each companion's level (CompanionsInput), and the star level of EVERY artifact and its potential lines
          (ArtifactsInput), the equipped artifacts and your cube gear (the PotentialCubes sheet: rarity, pity count and the three lines of each of the 15 slots, Potential and Bonus Potential; they appear on the Cubes tab).  A
          line whose stat is unknown is left empty, and a stat the slot cannot roll, a pity count above the cap or an unknown rarity is listed under Warnings.
        </li>
        <li>
          <strong>What is not</strong>: anything the workbook computes (derived cells, DPS results, the Sensitivity / Skills / Calc sheets), and the Equipment Compare sheet.  The app keeps one equipped set while the workbook has one per content type: you choose which content type's artifact loadout to import (the workbook's selected
          one by default).  The workbook has 4 artifact slots, the game (and this app) 5: the fifth is yours to fill after the import.  Potential-line stats the app does not know are listed under Warnings and left empty.  Formula cells are only read when the file holds a saved result for them.
        </li>
        <li>
          <strong>Values outside the allowed range</strong> (a typo, a placeholder) are imported as typed and listed under Warnings; blank cells and values that cannot be read fall back to the defaults.
        </li>
        <li>
          <strong>Privacy</strong>: the workbook is opened and parsed in your browser.  It is never uploaded; the only thing fetched from the server is the class definition, exactly as when you switch class.
        </li>
        <li>
          <strong>Not supported</strong>: macro-enabled (.xlsm) or binary (.xlsb) files, old .xls files and password-protected workbooks.  Open them in Excel and use Save As .xlsx first.
        </li>
      </ul>
    </>
  ),
};

export const WHICH_STATS_INTRO = (
  <>
    <p>
      Type the numbers shown <strong>on your in-game character stat screen</strong>, as they are after everything you wear and have unlocked, not the base values of a single item.  The model does not
      add anything for artifacts you list as baked in (next section): they are already inside the stat screen numbers.
    </p>
    <p>Every field has a short hint under it; here are the hints for the class you have selected.  Numbers outside a field's allowed range are rejected with a message under the field.</p>
  </>
);

export const NO_SCHEMA_HINTS = <p className="note">Load a class (header) to see its field hints here.</p>;

export const CONVENTIONS: HelpSection = {
  id: "help-conventions",
  title: "Modelling conventions",
  body: (
    <>
      <h4>Artifacts and your typed stats</h4>
      <ul>
        <li>
          <strong>Stats you type already include these artifacts</strong>: Book of Ancient, Athena Pierce's Old Gloves, Clear Spring Water, Soul Pouch, Lit Lamp, Star Rock, Cursed Doll and Shamaness Marble,
          plus Reindeer's Spear's base Defense Penetration and Bottle of Emotion's Final Damage.  Do not add them again.  The Artifacts tab marks them "baked into your stats".
        </li>
        <li>
          The Artifacts tab's equip ranking is a <strong>what-if</strong>: for those baked-in artifacts the gain is computed on top of the typed stats (equipping it, or removing it, from your current state), so it tells you
          what it is worth even though it does not change the main result.  The effects that are not baked in (for example Reindeer's Spear's Attack % and its extra boss / PvP effect, Bottle of Emotion's Attack %) are
          live and do change your Total DPS.
        </li>
        <li>
          <strong>Five artifact slots</strong>: the game has five, the workbooks only four.  The results for up to four equipped artifacts match the workbooks; with five the engine adds the fifth artifact's
          already verified effect to the same buckets (nothing in an effect depends on which slot it sits in), but that combination cannot be checked against Excel.  Order does not matter and an artifact counts once.
        </li>
        <li>
          <strong>Seven artifacts have no DPS effect in the model</strong> (Pig's Ribbon, Mushmom's Cap, Zakum's Stone Piece, Horntail's Scale, Pink Bean's Giant Rib, Lunar Dew, Ancient Text Piece): their stat is
          not used by the model or their content (raids, Guild Conquest) is not modelled.  They are listed greyed with the reason.
        </li>
      </ul>
      <h4>Boss and normal monsters, fight length</h4>
      <ul>
        <li>
          Content with both bosses and normal monsters (Breakthrough, Hero Dungeon) is a <strong>time-weighted blend</strong> of the boss and the normal-monster damage; "Boss/Normal Emphasis" sets how the time splits.
          The Stat values ranking blends the stats' <em>relative</em> gains by that same time weight, so a stat is not favoured just because normal-monster damage numbers are bigger.
        </li>
        <li>
          Fixed-length contents (World Boss, dungeons, PvP) are simulated for their real length; Chapter Hunt is a steady state.  When the fight has a stun or KO window (a stunning companion, KO phases, Status Effect
          Damage) and a single target, the model switches to a <strong>second-by-second schedule</strong>: it casts your buffs and cooldown skills at the moments that pay most, and damage inside a stun or KO second is
          multiplied.
        </li>
      </ul>
      <h4>Companions</h4>
      <ul>
        <li>
          A companion is summoned for <strong>30 s x (1 + Summoning Time Increase %)</strong> with a <strong>90 s cooldown</strong>.  It can be summoned from <strong>7 s</strong> into a fight at the earliest, and the best
          summon time (including waiting for a Hexagon Necklace stack) is chosen for you.
        </li>
        <li>
          Cast timing: the companion starts attacking after a 0.3 s delay and recasts with a period of cooldown + 0.5 s.  Because of that, breakpoints matter: for example Blaze Wizard's third stun cast needs
          +13.667% Summoning Time, so +13% gains almost nothing over +12% and +15% gains a lot (the Companions tab flags such "step" rows).
        </li>
        <li>
          <strong>Arwen's Glass Shoes</strong> adds +20% (star 0) up to +40% (star 5) Summoning Time while equipped; it is added on top of the value you type.
        </li>
        <li>
          A companion uses your stats at the moment of the summon, scaled by its level multiplier; it does not benefit from skill levels, Basic Attack Target Increase, Buff Duration or cooldown decrease.
        </li>
      </ul>
      <h4>Reading the Stat values tab</h4>
      <ul>
        <li>
          <strong>Units per +1% DPS: lower is better.</strong>  It is how many units of that stat give +1% Total DPS, so a smaller number means each unit is worth more.  "n/a" means one step gives no gain at all.
        </li>
        <li>
          Units differ between stats (+1 flat INT is not +1 percentage point): compare the % gain per step, or the units against what a unit costs you in game.  Critical Rate above 100% is priced as Critical Damage
          unless Ring of Cycles or Book of Ancient is equipped, which keep using the excess.
        </li>
      </ul>
    </>
  ),
};

/** Genuinely important assumptions (at most ~12), condensed from KNOWN_GAPS.md. */
export const LIMITATIONS: ReactNode[] = [
  <>
    <strong>No MP consumption.</strong>  The game's MP costs have no scaling data on either data source, so every skill is assumed castable.  Crowd control, accuracy / evasion, defense, healing and movement have no
    DPS meaning here and are not modelled.
  </>,
  <>
    <strong>Some skill curves are assumptions.</strong>  Where the game tables give only a level-1 value, the growth shape is assumed.  Bishop's Divine Protection has only its level-1 value (25% Defense) and an assumed
    curve; a few Paladin, Buccaneer and Corsair skills (for example Greater Sea Serpent I's 430% line) also use assumed curve shapes.  Cooldowns, hit counts and ratios mostly come from the game's own tables.
  </>,
  <>
    <strong>Proc rules.</strong>  A chance proc rolls once per attack per enemy hit, not per damage line.  "When attacking, X% chance, 1 s cooldown" masteries use a steady-state rate with the combined cast rate of
    basic attacks and action-costing damage skills (summons and damage-over-time ticks do not trigger them).  Internal cooldowns of these procs are not shortened by Skill Cooldown Decrease.  A few Final Attack folds
    (Hero, Paladin, Dark Knight) still count per damage line rather than per attack.
  </>,
  <>
    <strong>Steady-state approximations.</strong>  Stack, resource and uptime mechanics (Buccaneer's Assault Mode and Serpent Scales, Hero's combo stacks, Marksman's Blink Bolt, Paladin's Vessel of Light) are modelled as
    averages or duty cycles, not exact state machines.  Marksman's Blink Bolt is probably a slight overestimate.
  </>,
  <>
    <strong>Skill damage masteries multiply.</strong>  A "+70%" skill mastery is modelled as x1.7 of that skill's damage and the basic-attack chain is summed first, then multiplied.  This was measured in game for FP-Mage;
    the other classes assume the same rule.
  </>,
  <>
    <strong>HP- and condition-based passives are not modelled</strong> (for example Buccaneer's Perseverance, Corsair's Fullmetal Jacket defense penetration mastery, Groggy Mastery's conditional Final Damage): assumed to
    be inside the stats you type.
  </>,
  <>
    <strong>Unmodelled debuff and setup effects</strong>: Corsair's Swift Fire Weaken and the Siege Bomber / Broadside "Setup" masteries, Paladin's Divine Judgment +30% Basic Attack Damage buff, and Bowmaster's
    Hurricane attack-speed behaviour are left out.  Corsair's Bombardment (level 118) is a large part of its DPS and is worth an in-game check.
  </>,
  <>
    <strong>Unverified in game</strong>: Ice / Lightning Mage's Elquines strike-interval mastery (level and value), Illusion Step at level 118 (Bowmaster / Marksman), and Hero's Puncture wound debuff.
  </>,
  <>
    <strong>Artifacts</strong>: all 36 are listed and the equip effects of the live ones are modelled.  The potential lines of the Artifacts table are a reference / what-if tool only: they never change the main
    result.  Artifacts that need their stat typed in (baked in) only show a what-if gain.  The game has 5 artifact slots, the workbooks 4: with 5 equipped the app combines the verified per-artifact effects
    itself, which cannot be checked against Excel.
  </>,
  <>
    <strong>Companion and timeline simplifications</strong>: companions follow the user-provided kits and the rules above; a stun on normal monsters gets no timing alignment, Candle / Chalice / Ring of Cycles
    stay at their fight averages and only Hexagon Necklace and Charm of the Undead are resolved second by second.
  </>,
  <>
    <strong>Stat values, Cubes and Equipment compare</strong> are available for the classes marked in the table above; the others show "not available for this class yet".
  </>,
  <>
    <strong>Game data moves.</strong>  The numbers follow the data sources at the time of the last audit and the patch notes up to then (mainly maplestoryidle.info's game tables and the community wiki); a patch can
    make a value stale.  Treat differences of a percent or two as noise.
  </>,
];

/** Shown only in builds where the optional accounts feature is configured (see lib/cloud/config.ts).  The id is linked from the sign-in privacy note. */
export const ACCOUNTS: HelpSection = {
  id: "help-accounts",
  title: "Accounts (sign in with Google)",
  body: (
    <>
      <p>
        Signing in is optional.  Without an account everything works as before and your profiles stay in this browser.  With a Google account your <strong>profiles</strong> (and two small settings: the
        theme and the last class you used) can follow you to other browsers and devices.
      </p>
      <h4>What is saved, and when</h4>
      <ul>
        <li>
          <strong>Saved</strong>: each profile you saved on the Profiles tab (the stats, artifacts, companion levels and cube / equipment lines it holds), its name and the time it was last changed; your theme and
          last class; and your Google account id and e-mail address (kept by Google sign-in).  Nothing else, and no analytics or advertising cookies.
        </li>
        <li>
          <strong>Save to account</strong> (account menu, or the Profiles tab) is the only thing that writes to the cloud: it copies just the profiles that changed since the last save, in one go.  Editing
          alone never uploads anything; changed profiles are marked with an <em>unsaved</em> cloud icon (and a dot on your avatar) and the browser warns before you close the tab with unsaved changes.
        </li>
        <li>
          <strong>Refresh from account</strong> reads your account again and merges it with this device.  The app also does this once when you sign in; it does not listen for changes in the background.
        </li>
        <li>
          <strong>First sign-in</strong> on a browser that already holds profiles asks whether to upload them (all, some or none).  Profiles you keep on this device only are marked <em>local only</em>.
        </li>
      </ul>
      <h4>Two devices, one profile</h4>
      <p>
        Profiles are matched by an id, and the <strong>newest edit wins</strong> (by the time of the last change, so keep your devices' clocks right).  When the same profile was changed on two devices, the version
        that lost is kept on this device under <em>Version history</em> (account menu) and a notice tells you; <em>Restore as new profile</em> puts it back.  A profile deleted on one device is deleted on the others
        at their next refresh (the cloud keeps a small marker for 30 days).
      </p>
      <h4>Limits</h4>
      <p>An account holds up to 50 profiles; a single profile must stay under about 180 KB (far more than a normal profile).  Profiles that do not fit are left out with a message, never dropped silently.</p>
      <h4>Privacy and deleting your data</h4>
      <ul>
        <li>
          Your data is stored in Google Firebase (Authentication and the Firestore database); security rules let only your own signed-in account read or write it.  The person running this site can, as an
          administrator of the Firebase project, technically see stored data: do not put anything in a profile name that you would not want them to see.
        </li>
        <li>
          <strong>Download all my data (JSON)</strong> (account menu) gives you everything stored for your account.
        </li>
        <li>
          <strong>Delete my account and data</strong> (account menu) asks you to type DELETE and to sign in with Google once more, then removes all your documents and the sign-in account.  Profiles that are on
          this device stay here as ordinary local profiles.
        </li>
        <li>
          <strong>Sign out</strong> lets you keep this browser's profiles or clear them.  The Google sign-in is remembered by your browser until you sign out.
        </li>
      </ul>
    </>
  ),
};
