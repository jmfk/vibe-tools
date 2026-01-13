---
id: PRD-037
title: Google Sheets Integration
type: FEATURE
status: done
group: null
depends_on: []
created_at: '2026-01-13T18:35:15.017458'
updated_at: '2026-01-13T19:03:32.403972'
discussion_id: D_kwDOQzI0Lc4AjoM1
discussion_url: https://github.com/jmfk/vibe-tools/discussions/52
last_synced_at: '2026-01-13T19:03:32.403861'
sync_hash: 9fa84eab64b1bfa2052e59fd45e872e539e9e4e7b89436585895e6d53c323a7d
---

# Google Sheets Integration

## Overview
- **Problem statement**: Teams need to log LLM costs to Google Sheets for centralized tracking, analysis, and sharing. The system should support OAuth2 and service account authentication, handle errors gracefully, and provide fallback to CSV.
- **User benefits**: Centralized cost tracking in Google Sheets, easy sharing and analysis, automatic logging, and integration with existing workflows.
- **Success criteria**: Google Sheets integration successfully logs costs, handles authentication correctly, provides error handling, and falls back to CSV when needed.

## Feature Inspiration
The Google Sheets integration extends the cost tracking system to log costs to a Google Sheet in addition to CSV. It supports OAuth2 (browser login) and service account authentication, handles API errors gracefully, and falls back to CSV logging if Google Sheets fails.

**Key capabilities**:
- Google Sheets API integration
- OAuth2 authentication (browser login)
- Service account authentication
- Automatic row appending
- Error handling and fallback
- Sheet ID configuration

## Frontend
N/A - Background integration.

## Backend
- **Authentication Methods**:
  - **OAuth2**: Browser-based login, stores credentials in `.vibe_authorized_user.json`
  - **Service Account**: Service account key in `.vibe_google_creds.json`
  - Preference: OAuth2 first, fallback to service account
- **Setup Process** (`vibe-setup google`):
  - Prompts for Google Sheet ID
  - Guides OAuth2 setup (client secrets, authorization)
  - Or configures service account
  - Saves sheet ID to `.vibe_config.json`
- **Logging Process**:
  1. Check if Google Sheets enabled in config
  2. Check for credentials (OAuth2 or service account)
  3. Authenticate with gspread library
  4. Open sheet by ID or name
  5. Append row with cost data
  6. Handle errors, fallback to CSV
- **Error Handling**:
  - API errors (404, permissions, etc.)
  - Missing credentials
  - Network errors
  - Falls back to CSV logging with warning
- **Sheet Structure**: 
  - Uses first worksheet (index 0)
  - Appends rows (assumes header row exists or creates)
  - Same columns as CSV: Timestamp, PRD, Phase, Iteration, Agent, Model, Input Tokens, Output Tokens, Cost (USD), Purpose

## Infrastructure
- **Google Sheets API**: Uses gspread library.
- **Authentication**: OAuth2 or service account credentials.
- **Configuration**: Sheet ID in `.vibe_config.json`.
- **Fallback**: CSV logging if Google Sheets fails.

## Architecture and Constraints
- **gspread Dependency**: Requires gspread library.
- **Authentication Complexity**: OAuth2 setup can be complex for users.
- **Error Handling**: Must gracefully handle API errors, network issues.
- **Fallback**: Always falls back to CSV, never loses data.

## Success Criteria
- OAuth2 authentication works
- Service account authentication works
- Costs logged to Google Sheets
- Error handling robust
- CSV fallback works
- Setup process clear

## Acceptance Tests
1. **OAuth2 Setup**: Run `vibe-setup google`, verify OAuth2 setup works
2. **Service Account Setup**: Configure service account, verify works
3. **Cost Logging**: Run agent operation, verify logged to Google Sheets
4. **Error Handling**: Test with invalid sheet ID, verify error handling
5. **Fallback**: Disable internet, verify CSV fallback works
6. **Sheet Structure**: Verify rows appended correctly, format correct
7. **Multiple Operations**: Run multiple operations, verify all logged