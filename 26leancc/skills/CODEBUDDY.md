# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## Project Overview

This is an **AI Skill Definition Repository** containing declarative skill configurations for AI assistants. Skills are defined using Markdown files with YAML frontmatter, not traditional executable code.

## Architecture

```
skills/
└── .codebuddy/
    └── skills/
        └── {skill-name}/
            ├── SKILL.md              # Entry point with name, description, and workflow
            ├── rules/                # Guidelines and standards
            ├── templates/            # Output format definitions  
            └── workflow/             # Sequential process steps
```

### Skill Structure Pattern

Each skill follows a modular architecture:
- **SKILL.md**: Main entry with YAML frontmatter (`name`, `description`) and workflow overview
- **workflow/**: Step-by-step instructions (step1-xxx.md, step2-xxx.md, etc.)
- **rules/**: Writing/behavior guidelines
- **templates/**: Output templates with `{placeholder}` syntax

### Current Skills

| Skill | Location | Trigger | Purpose |
|-------|----------|---------|---------|
| `weekly-report-ai` | `.codebuddy/skills/weekly-report-ai/` | "写周报", "帮我总结本周工作" | Generate professional weekly work reports |

## Development Workflow

Since this is declarative configuration (no executable code):
- **No build/test/lint commands** - files are Markdown only
- Edit `.md` files directly
- Test by invoking skills in an AI assistant environment

## Conventions

- All content is in **Simplified Chinese**
- Use emoji headers for visual organization in templates
- Keep workflow steps as separate files for modularity
- SKILL.md must have YAML frontmatter with `name` and `description`

## Known Issues

- `weekly-report-ai/workflow/setp3-generate.md` has a typo in filename (should be `step3`)
- SKILL.md references `step3-generate.md` but actual file is `setp3-generate.md`
