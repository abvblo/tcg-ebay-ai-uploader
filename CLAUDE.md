# CLAUDE.md - Project-Specific Instructions for Claude

## CRITICAL: Always Use Sub-Agents (Task Tool)

### When to Deploy Sub-Agents:
1. **ALWAYS when user mentions "sub-agents", "agents", or "deploy agents"**
2. **For parallel tasks** - When multiple independent tasks can be done simultaneously
3. **For complex analysis** - When analyzing large codebases or multiple files
4. **For batch operations** - When making similar changes across multiple files

### How to Use Sub-Agents Effectively:
```
1. Use TodoWrite to plan tasks first
2. Deploy multiple Task agents in a SINGLE function call for parallel execution
3. Each agent should have a specific, focused task
4. Agents work best for search, analysis, and batch operations
```

### Example Pattern:
When user says "deploy agents" or "use sub-agents":
1. First analyze what needs to be done
2. Create todo list with TodoWrite
3. Deploy multiple Task agents in parallel for different aspects
4. Update todos as tasks complete

## Project-Specific Commands

### Linting and Type Checking:
- Run `npm run lint` after making code changes
- Run `npm run typecheck` for TypeScript validation
- Always run these before marking tasks as complete

### Testing:
- Check README or package.json for test commands
- Never assume test framework - always verify first

## eBay TCG Batch Uploader Specific Notes

### Image Input Folder:
- Images should be placed in the `input` folder (not "Scans")
- The system uses AI (Ximilar) to identify trading cards
- Supports Pokemon and Magic: The Gathering cards

### Key Directories:
- `input/` - Place card images here
- `output/` - Generated Excel files and reports
- `src/` - Main application code
- `config/` - Configuration files

### Important Files:
- `config.json` - Main configuration
- `src/config.py` - Configuration handler (defaults to "input" folder)
- `src/main.py` - Entry point

## Remember:
- ALWAYS use sub-agents when explicitly requested
- Deploy agents in parallel when possible
- Use TodoWrite to track all tasks
- Run lint/typecheck before completing code tasks