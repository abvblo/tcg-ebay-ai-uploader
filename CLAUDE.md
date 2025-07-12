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

## API Loop and Crash Prevention

### Detecting API Loops:
1. **Watch for repeated similar API calls** - If making the same request multiple times
2. **Monitor error patterns** - Same error occurring repeatedly
3. **Check for infinite recursion** - Function calling itself without exit condition
4. **Look for missing break conditions** - Loops without proper termination

### Breaking Out of API Loops:
1. **Implement retry limits**:
   ```python
   MAX_RETRIES = 3
   retry_count = 0
   while retry_count < MAX_RETRIES:
       try:
           # API call here
           break
       except Exception as e:
           retry_count += 1
           if retry_count >= MAX_RETRIES:
               raise Exception(f"Max retries exceeded: {e}")
   ```

2. **Add exponential backoff**:
   ```python
   import time
   for attempt in range(MAX_RETRIES):
       try:
           # API call here
           break
       except Exception as e:
           wait_time = 2 ** attempt  # 1, 2, 4 seconds
           time.sleep(wait_time)
   ```

3. **Use circuit breakers**:
   - Track consecutive failures
   - Temporarily disable problematic operations
   - Provide fallback behavior

### Preventing Crashes:
1. **Always validate API responses**:
   ```python
   if response and hasattr(response, 'data'):
       # Process response
   else:
       # Handle missing data gracefully
   ```

2. **Implement proper error handling**:
   - Catch specific exceptions, not broad except blocks
   - Log errors with context for debugging
   - Provide user-friendly error messages

3. **Monitor rate limits**:
   - Check API documentation for rate limits
   - Implement request throttling
   - Use batch operations when available

### Emergency Escape Strategies:
1. **If stuck in a loop**: 
   - Stop current operation
   - Analyze the pattern causing the loop
   - Implement a different approach
   
2. **If API is unresponsive**:
   - Check network connectivity
   - Verify API credentials/keys
   - Try alternative endpoints or methods
   
3. **If getting repeated errors**:
   - Change approach entirely
   - Break down the task into smaller parts
   - Use sub-agents for parallel processing

## Remember:
- ALWAYS use sub-agents when explicitly requested
- Deploy agents in parallel when possible
- Use TodoWrite to track all tasks
- Run lint/typecheck before completing code tasks
- Implement retry limits and error handling for all API calls
- Break out of loops early when detecting repetitive patterns