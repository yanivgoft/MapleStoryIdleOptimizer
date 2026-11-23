# Golden refresh log

Every line below is a refresh of golden JSON files FROM THE CURRENT ENGINE (`python3 tests/golden/update_goldens.py ... --write --reason "..."`).

**A refreshed golden pins the ENGINE's own behaviour.** The goldens were originally frozen from the Excel verify scripts / workbooks (independent implementations
of the model); once a value has been refreshed here it is no longer an independent workbook value, only a regression pin of the engine as it was at the commit in
the table.  Review every refresh like a code change (the dry-run summary shows which fields moved and by how much).  The JSON files carry no refresh marker: this
table is the only provenance.  `HEAD` is the git commit the engine was built on; `+dirty` = uncommitted changes under engine/ at the time.

| date | class | kind | HEAD | cases changed | values changed | max rel diff | reason |
|---|---|---|---|---|---|---|---|
