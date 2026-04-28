# 目录布局

```text
strategy-material-engine/
├── SKILL.md
├── references/
│   ├── layout.md
│   ├── schemas.md
│   ├── workflows.md
│   ├── buildmate/
│   └── materials/
├── scripts/
├── sources/
│   ├── buildmate/
│   └── materials/
├── assets/
│   ├── cases/
│   ├── case_drafts/
│   └── materials/
├── cases -> assets/cases
├── case_drafts -> assets/case_drafts
├── materials -> assets/materials
├── index/
│   ├── cases/
│   ├── materials/
│   ├── sources/
│   └── unified/
├── evals/
├── expert_models/
├── strategy_models/
└── stage4_models/
```

## 设计原则

- `sources/` 只放原始来源，不做重写。
- `assets/cases/` 只放可复用商业执行链案例。
- `assets/materials/` 只放原子化素材。
- `index/` 分桶建索引，避免不同粒度对象互相污染。
- `expert_models/`、`strategy_models/`、`stage4_models/` 属于运行能力层，不直接参与素材存储。

## sources 子目录

- `sources/buildmate/`：更偏项目实操、精华帖、商业案例原文
- `sources/materials/`：更偏观点文、情感文、研究笔记、逐字稿

注意：这只是来源分桶，不代表后续一定建 case 或一定只出 material。

## assets/materials 类型目录

建议至少保留这些类型子目录：

- `story/`
- `insight/`
- `data/`
- `method/`
- `quote/`
- `association/`
- `playbook/`
