# Template System

## Overview
- **Problem statement**: Projects need prompt templates and file templates that can be customized per project while maintaining defaults. The system should support template management, project-specific overrides, and template initialization.
- **User benefits**: Customizable prompts, project-specific templates, easy template management, and default templates for common scenarios.
- **Success criteria**: Template system successfully manages templates, supports project overrides, initializes templates correctly, and provides useful default templates.

## Feature Inspiration
The template system manages prompt templates and file templates. Templates are stored in `prompts/` directory, can be customized per project, and are loaded with project-specific versions taking precedence over package defaults.

**Key capabilities**:
- Template storage (prompts/, project-specific)
- Template loading (package defaults + project overrides)
- Template initialization
- Template management

## Frontend
N/A - Background system, used by other components.

## Backend
- **Template Storage**: 
  - Package templates: In package `prompts/` directory
  - Project templates: In project `prompts/` directory
  - Project templates override package templates
- **Template Loading**: 
  - `get_prompt(filename)`: Loads prompt template
  - Checks project `prompts/` first
  - Falls back to package `prompts/`
  - Returns template content
- **Template Initialization**: 
  - `vibe init` copies package templates to project
  - Allows project customization
  - Preserves package defaults
- **Template Types**: 
  - Prompt templates (`.txt` files)
  - May support other template types
- **Template Variables**: 
  - Templates support variable substitution
  - Uses `.format()` or similar
  - Variables provided by callers

## Infrastructure
- **File System**: Reads template files from directories.
- **Package Resources**: Accesses package templates.

## Architecture and Constraints
- **Template Format**: Plain text with variable placeholders.
- **Override Logic**: Project templates must exactly match package names.

## Success Criteria
- Templates loaded correctly
- Project overrides work
- Template initialization successful
- Variable substitution works

## Acceptance Tests
1. **Template Loading**: Load template, verify content correct
2. **Project Override**: Create project template, verify used
3. **Template Init**: Run init, verify templates copied
4. **Variable Substitution**: Test template with variables, verify substituted
