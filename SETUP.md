# Pillar VC Slackbot - Setup Guide

This guide walks you through setting up and deploying the Pillar VC Slackbot.

## Prerequisites

- Python 3.11 or higher
- A Slack workspace where you have permission to install apps
- An Anthropic API key (for Claude)
- (Optional) Google Cloud project for Docs integration
- (Optional) Airtable account and API key

## Step 1: Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Name it "Pillar VC Bot" and select your workspace
4. Click **Create App**

### Configure Bot Token Scopes

1. In the left sidebar, go to **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Add these scopes:
   - `channels:history` - Read messages in public channels
   - `channels:read` - View basic channel info
   - `chat:write` - Send messages
   - `commands` - Add slash commands
   - `files:read` - View files shared in channels
   - `groups:history` - Read messages in private channels
   - `groups:read` - View basic private channel info
   - `im:history` - Read DM messages
   - `im:read` - View basic DM info
   - `im:write` - Send DMs
   - `mpim:history` - Read group DM messages
   - `mpim:read` - View group DM info
   - `reactions:write` - Add reactions
   - `users:read` - View user info

### Enable Socket Mode

1. Go to **Socket Mode** in the left sidebar
2. Toggle **Enable Socket Mode** ON
3. When prompted, create an app-level token:
   - Name: `socket-token`
   - Scope: `connections:write`
4. Copy the token (starts with `xapp-`) - you'll need this later

### Add Slash Command

1. Go to **Slash Commands** in the left sidebar
2. Click **Create New Command**
3. Fill in:
   - Command: `/pillar`
   - Short Description: `Pillar VC Bot commands`
   - Usage Hint: `[summarize|actions|agenda|portfolio|help]`
4. Click **Save**

### Enable Events

1. Go to **Event Subscriptions** in the left sidebar
2. Toggle **Enable Events** ON
3. Expand **Subscribe to bot events**
4. Add these events:
   - `app_mention` - When someone @mentions the bot
   - `message.channels` - Messages in public channels
   - `message.groups` - Messages in private channels
   - `member_joined_channel` - When someone joins a channel

### Enable Interactivity (for modals)

1. Go to **Interactivity & Shortcuts**
2. Toggle **Interactivity** ON
3. (Leave Request URL blank - Socket Mode handles this)

### Install the App

1. Go to **Install App** in the left sidebar
2. Click **Install to Workspace**
3. Review permissions and click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### Get Signing Secret

1. Go to **Basic Information**
2. Scroll to **App Credentials**
3. Copy the **Signing Secret**

## Step 2: Get API Keys

### Anthropic (Claude) API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in or create an account
3. Go to **API Keys**
4. Create a new key and copy it

### Google Cloud (Optional - for Docs integration)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable these APIs:
   - Google Docs API
   - Google Drive API
4. Go to **APIs & Services** → **Credentials**
5. Click **Create Credentials** → **OAuth client ID**
6. Select **Web application**
7. Add `http://localhost:8080/oauth/callback` to Authorized redirect URIs
8. Copy the **Client ID** and **Client Secret**

### Airtable (Optional)

1. Go to [airtable.com/account](https://airtable.com/account)
2. Generate a personal access token with these scopes:
   - `data.records:read`
   - `data.records:write`
   - `schema.bases:read`
3. Copy your Base ID from the Airtable URL (it's in the URL when viewing your base)

## Step 3: Configure Environment

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```
   # Required
   SLACK_BOT_TOKEN=xoxb-your-token
   SLACK_APP_TOKEN=xapp-your-token
   SLACK_SIGNING_SECRET=your-signing-secret
   ANTHROPIC_API_KEY=sk-ant-your-key

   # Optional (for Google Docs)
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret

   # Optional (for Airtable)
   AIRTABLE_API_KEY=your-airtable-key
   AIRTABLE_BASE_ID=your-base-id
   ```

## Step 4: Run Locally

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the bot:
   ```bash
   python app.py
   ```

4. You should see:
   ```
   Starting Pillar VC Bot in Socket Mode...
   Bot is ready! Use /pillar help in Slack to get started.
   ```

5. Test in Slack:
   - Type `/pillar help` in any channel
   - @mention the bot: `@Pillar VC Bot summarize this channel`

## Step 5: Deploy to Railway (Recommended)

Railway is the easiest deployment option for beginners.

### Setup

1. Create a GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Push to GitHub:
   ```bash
   gh repo create pillar-slackbot --private --source=. --push
   ```
   Or use GitHub's web interface to create and push.

3. Go to [railway.app](https://railway.app)
4. Sign in with GitHub
5. Click **New Project** → **Deploy from GitHub repo**
6. Select your repository

### Configure Environment Variables

1. In Railway, go to your project
2. Click on your service
3. Go to **Variables**
4. Add all variables from your `.env` file:
   - `SLACK_BOT_TOKEN`
   - `SLACK_APP_TOKEN`
   - `SLACK_SIGNING_SECRET`
   - `ANTHROPIC_API_KEY`
   - (and optional Google/Airtable vars)

### Deploy

Railway automatically deploys when you push to GitHub. Check the **Deployments** tab for logs.

## Airtable Setup (Optional)

If using Airtable for portfolio data, create these tables:

### Portfolio Companies Table
- Name (Single line text) - Primary field
- Stage (Single select): Seed, Series A, Series B, Growth
- Sector (Single select): SaaS, Fintech, Healthcare, etc.
- Lead Partner (Single line text)
- Investment Date (Date)
- Last Valuation (Currency)
- Key Metrics (Long text)
- Last Board Meeting (Date)
- Notes (Long text)
- Slack Channel (Single line text) - e.g., "portfolio-acme"

### Pipeline Table
- Company Name (Single line text) - Primary field
- Status (Single select): New, In Review, Due Diligence, Term Sheet, Passed
- Sector (Single select)
- Deal Owner (Single line text)
- Deal Stage (Single select)
- Notes (Long text)
- Next Steps (Long text)

### Meeting Agenda Items Table
- Category (Single select): Investment Decisions, Pipeline Review, Portfolio Company Updates, Other Business
- Item (Long text)
- Submitted By (Single line text)
- Status (Single select): Pending, Included

## Portfolio Channel Naming Convention

For automatic portfolio company detection, name channels with a consistent prefix:
- `portfolio-acme-corp`
- `portfolio-beta-startup`
- `portfolio-gamma-tech`

The default prefix is `portfolio-`. You can change this with the `PORTFOLIO_CHANNEL_PREFIX` environment variable.

## Usage

### Slash Commands

| Command | Description |
|---------|-------------|
| `/pillar help` | Show all commands |
| `/pillar summarize` | Summarize last 24 hours |
| `/pillar summarize 7d` | Summarize last 7 days |
| `/pillar catchup` | Personal catch-up since last visit |
| `/pillar actions` | Extract action items |
| `/pillar actions @user` | Action items for specific user |
| `/pillar agenda` | Start agenda builder |
| `/pillar agenda add investment [item]` | Add investment decision item |
| `/pillar agenda add pipeline [item]` | Add pipeline item |
| `/pillar agenda add portfolio [item]` | Add portfolio update |
| `/pillar agenda finalize` | Create Google Doc |
| `/pillar portfolio` | List portfolio companies |
| `/pillar portfolio [company]` | Get company update |
| `/pillar lp-letter` | Generate LP letter draft |
| `/pillar lp-letter Q4 2024` | Generate for specific quarter |

### Mentions

You can also @mention the bot with natural language:
- `@Pillar VC Bot summarize the last week`
- `@Pillar VC Bot what are the action items?`
- `@Pillar VC Bot catch me up`
- `@Pillar VC Bot what's new with Acme Corp?`

## Troubleshooting

### Bot doesn't respond
- Check that the bot is running (Socket Mode connected)
- Verify the bot is invited to the channel
- Check Railway/local logs for errors

### "Missing required environment variables" error
- Ensure all required variables are set
- Check for typos in variable names

### Google Docs not working
- Complete the OAuth flow by clicking the "Connect Google Account" button
- Verify your Google Cloud credentials are correct
- Check that APIs are enabled in Google Cloud Console

### Airtable not finding companies
- Check that table and field names match exactly
- Verify your API key has correct permissions
- Ensure Base ID is correct

## Support

For issues or questions, contact the Pillar VC tech team or open an issue in the repository.
