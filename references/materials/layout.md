# Layout

Use this skill directory layout:

```text
strategy-material-engine/
├── SKILL.md
├── references/
├── scripts/
├── sources/
│   ├── buildmate/
│   └── materials/
├── assets/
│   ├── cases/
│   ├── case_drafts/
│   └── materials/
├── materials/        # symlink -> assets/materials
├── cases/            # symlink -> assets/cases
├── case_drafts/      # symlink -> assets/case_drafts
│   ├── story/
│   ├── insight/
│   ├── data/
│   └── method/
└── index/
    ├── cases/
    ├── materials/
    └── sources/
```

## Rules

- Put raw long-form inputs in `sources/materials/`
- Put processed atomic writing units in `assets/materials/`
- Put generated search artifacts in `index/`
- Keep file names short, readable, and stable
- Prefer one material per file
