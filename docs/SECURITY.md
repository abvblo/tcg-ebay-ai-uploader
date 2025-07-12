# Security Documentation - eBay TCG Batch Uploader

## Overview
This document outlines the security measures implemented to protect API keys, credentials, and sensitive data in the eBay TCG Batch Uploader project.

## Security Measures Implemented

### 1. Environment Variable Protection
- **File**: `.env` (git-ignored)
- **Purpose**: Stores all sensitive credentials and API keys
- **Security**: Automatically ignored by git, never committed to version control

### 2. Configuration Template
- **File**: `.env.template`
- **Purpose**: Provides setup guidance without exposing secrets
- **Content**: Contains placeholder values for all required credentials

### 3. Git Ignore Configuration
- **File**: `.gitignore`
- **Protected Files**:
  - `.env` (all variants)
  - `config.json`
  - `*.key`, `*.pem`, `*.p12`
  - `secrets.json`

### 4. Application-Level Validation
- **File**: `src/config.py`
- **Features**:
  - Validates API keys are not placeholder values
  - Fails gracefully when credentials are missing
  - Provides clear error messages for security issues
  - Warns when optional credentials are placeholder values

### 5. Security Verification
- **File**: `scripts/maintenance/verify_security.py`
- **Purpose**: Automated testing of security measures
- **Tests**:
  - .gitignore configuration
  - Template file integrity
  - No real credentials in tracked files
  - Config validation functionality

## Credential Management

### Required Credentials
- `XIMILAR_API_KEY`: Card identification API
- `POKEMON_TCG_API_KEY`: Pokemon card data API
- `OPENAI_API_KEY`: Title optimization (optional)
- `EBAY_APP_ID`, `EBAY_DEV_ID`, `EBAY_CERT_ID`, `EBAY_USER_TOKEN`: eBay integration
- Database credentials: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`

### Setup Process
1. Copy `.env.template` to `.env`
2. Replace all placeholder values with actual credentials
3. Verify setup with `python scripts/maintenance/verify_security.py`
4. Run application - it will fail if placeholder values are detected

## Security Best Practices

### For Developers
1. **Never commit `.env` files** - They are git-ignored for a reason
2. **Always use `.env.template`** - Update it when adding new credentials
3. **Run security verification** - Use `python scripts/maintenance/verify_security.py` before commits
4. **Review git status** - Ensure no sensitive files are staged

### For Production
1. **Use environment variables** - Set credentials directly in production environment
2. **Rotate credentials regularly** - Update API keys and tokens periodically
3. **Monitor access logs** - Track API usage and potential security issues
4. **Use secure credential storage** - Consider using services like AWS Secrets Manager

## Emergency Procedures

### If Credentials Are Exposed
1. **Immediately rotate all exposed credentials**
2. **Check git history** - Use `git log --oneline` to verify no commits contain secrets
3. **Update documentation** - Ensure all security measures are in place
4. **Notify relevant parties** - Inform API providers if necessary

### If Security Verification Fails
1. **Do not proceed** - Fix security issues before continuing
2. **Review recent changes** - Check what might have broken security
3. **Re-run verification** - Ensure all tests pass before proceeding

## Monitoring and Alerts

### Automated Checks
- Security verification script runs all tests
- Config validation prevents startup with placeholder values
- Git ignore prevents accidental commits

### Manual Reviews
- Regular security audits of credential usage
- Periodic review of API key permissions
- Monitoring of unusual API activity

## Compliance

### Data Protection
- No sensitive data stored in version control
- All credentials encrypted at rest (when using proper storage)
- API keys have minimum required permissions

### Access Control
- Credentials are only accessible to authorized personnel
- Development and production environments are separated
- API keys are scoped to specific functionality

## Contact Information

For security concerns or questions:
- Review this documentation first
- Run `python scripts/maintenance/verify_security.py` for automated checks
- Check application logs for security warnings
- Ensure all placeholder values are replaced with real credentials

## Version History
- **2025-07-11**: Initial security implementation
  - Added .env.template
  - Removed real credentials from tracked files
  - Implemented config validation
  - Added security verification script