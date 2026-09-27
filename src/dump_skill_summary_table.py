"""Read-only extraction: Name/FactorIndex/Cooldown/ProcChance/BaseDamage for every class's
skills, taken directly from each build_<class>_workbook.py's own SKILL_ROWS list, for
cross-class eyeballing (e.g. spotting factorIndex=0 outliers like Bowmaster's recent bugs)."""
import sys
import importlib

sys.path.insert(0, "src")

CLASSES = [
    ("Bishop", "build_bishop_workbook"),
    ("Bowmaster", "build_bowmaster_workbook"),
    ("Buccaneer", "build_buccaneer_workbook"),
    ("Corsair", "build_corsair_workbook"),
    ("Dark Knight", "build_dark_knight_workbook"),
    ("FP-Mage", "build_fp_mage_workbook"),
    ("Hero", "build_hero_workbook"),
    ("Ice-Lightning Mage", "build_ice_lightning_mage_workbook"),
    ("Marksman", "build_marksman_workbook"),
    ("Night Lord", "build_night_lord_workbook"),
    ("Paladin", "build_paladin_workbook"),
    ("Shadower", "build_shadower_workbook"),
]

COLS = ["Name", "Cooldown(s)", "ProcChance%", "BaseDamage(tenths%)", "FactorIndex"]


def fmt(v):
    s = "" if v is None else str(v)
    return s


def main():
    for class_name, mod_name in CLASSES:
        mod = importlib.import_module(mod_name)
        idx = {name: i for i, name in enumerate(mod.SKILL_COLUMNS)}
        print(f"\n=== {class_name} ===")
        header = f"{'Name':<32} {'FactorIdx':<10} {'Cooldown(s)':<28} {'ProcChance%':<14} {'BaseDamage(tenths%)':<20}"
        print(header)
        print("-" * len(header))
        for row in mod.SKILL_ROWS:
            name = fmt(row[idx["Name"]])
            fidx = fmt(row[idx["FactorIndex"]])
            cd = fmt(row[idx["Cooldown(s)"]])
            proc = fmt(row[idx["ProcChance%"]])
            base = fmt(row[idx["BaseDamage(tenths%)"]])
            print(f"{name:<32} {fidx:<10} {cd:<28} {proc:<14} {base:<20}")


if __name__ == "__main__":
    main()
