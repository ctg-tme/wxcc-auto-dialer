# Auto Dialer (WXCC Desktop)

Replay recorded audio into Webex Contact Center by combining Twilio calls with a Playwright-driven agent desktop session.
The workflow uploads customer audio to S3, injects agent audio into the browser microphone, and orchestrates calls for demos or testing.

## What it does

- Splits stereo WAV files into customer (left) and agent (right) channels.
- Uploads the customer channel to S3 with a public URL for Twilio playback.
- Automates the WXCC Agent Desktop login and call handling via Playwright.
- Supports sequential runs for multiple agents with different audio assignments.
- Includes a separate utility script (fetch_wav_files.py) to fetch recordings from WXCC APIs and upload WAVs manually.

## Requirements

- Python 3 and pip
- Twilio account credentials and a verified phone number
- AWS credentials with access to an S3 bucket (default: `liamfrawley` in `eu-north-1`, or configure your own)
- WXCC Agent Desktop credentials and URL
- Optional: `ffmpeg` if you use the legacy audio processor in `src/audioProcessor/`

## AWS credentials

Uploads use boto3's default credential chain (credentials are picked up automatically).
Configure a **shared credentials file** (`~/.aws/credentials`): Run `aws configure` to set up

### S3 bucket setup

Your S3 bucket must allow **public read access** so Twilio can fetch the WAV files. To set this up:

1. Create an S3 bucket in AWS Console
2. Disable "Block all public access" in the bucket's permissions
3. Add a bucket policy to allow public reads:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
    }
  ]
}
```

Replace `YOUR-BUCKET-NAME` with your actual bucket name.

## Setup

1. Create or update `config/config.json` with your credentials and audio inputs.

```json
{
  "TWILIO_ACCOUNT_SID": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "TWILIO_AUTH_TOKEN": "your_twilio_token",
  "TWILIO_PHONE_NUMBER": "+15551234567",
  "CONTACT_CENTER_PHONE_NUMBER": "+15557654321",
  "CUSTOMER_AUDIO_DELAY_SECONDS": 0.8,
  "KEEP_BROWSER_OPEN": false,
  "WRAP_UP_MODE": "auto",
  "AUDIO_WAV_FILES": [],
  "AGENT_DESKTOP_URL": "https://desktop.wxcc-eu2.cisco.com/",
  "S3_BUCKET": "your-bucket-name",
  "S3_REGION": "us-east-1",
  "S3_PREFIX": "audio-uploads/",
  "AGENT_AUDIO_ASSIGNMENTS": [
    {
      "agent": {
        "email": "agent-one@example.com",
        "password": "agent-one-password",
        "extension": "286271",
        "role": "Agent"
      },
      "audio_wav_files": [
        "audio/agent-one/intro.wav",
        "audio/agent-one/closing.wav"
      ]
    },
    {
      "agent": {
        "email": "agent-two@example.com",
        "password": "agent-two-password",
        "extension": "286272",
        "role": "Agent"
      },
      "audio_wav_files": ["audio/agent-two/demo.wav"]
    }
  ]
}
```

2. Source the setup script to create the virtual environment, install dependencies, and install Playwright browsers:

```bash
source setup.rc
# or
. setup.rc
```

3. If you use the audio processor tools in `src/audioProcessor/`, install ffmpeg:

```bash
brew install ffmpeg
```

## Run the fake call workflow

The main entry point reads from `config/config.json` and runs the orchestration:

```bash
python src/main.py
```

For each configured WAV file the script will:

1. Split stereo audio if needed and stage the agent channel for Playwright.
2. Upload the customer channel to S3 (configurable via `S3_BUCKET`, `S3_REGION`, `S3_PREFIX`).
3. Launch the agent desktop browser with the agent audio injected as a fake microphone.
4. Trigger a Twilio call that plays the customer audio after `CUSTOMER_AUDIO_DELAY_SECONDS`.

## Configuration reference

All settings are loaded from `config/config.json` and mapped into environment variables.

- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` for outbound calls.
- `CONTACT_CENTER_PHONE_NUMBER` for the destination dialed by Twilio.
- `AGENT_AUDIO_ASSIGNMENTS` list of agent-specific audio runs. Each entry contains:
  - `agent` credentials for the assignment.
  - `audio_wav_files` list of WAV paths or globs to run for that agent.
- `CUSTOMER_AUDIO_DELAY_SECONDS` to pause before Twilio plays customer audio (default 0.8s).
- `KEEP_BROWSER_OPEN` to keep the final agent browser open after the run.
- `WRAP_UP_MODE` optional wrap-up UI mode: `auto` (default), `legacy`, or `suggested`.
- `AGENT_DESKTOP_URL` to override the desktop URL (defaults to EU2).
- `S3_BUCKET` S3 bucket for customer audio uploads (default: `liamfrawley`).
- `S3_REGION` AWS region for the bucket (default: `eu-north-1`).
- `S3_PREFIX` key prefix for uploaded files (default: `audio-uploads/`).
- `AWS_PROFILE` optional AWS profile name for S3 credentials.

Notes:

- If a WAV is mono, it is used for both customer playback and agent injection.
- Stereo WAVs use left channel for customer audio and right channel for agent audio.
- Agent assignments run sequentially in randomized order on each run; there is no parallel dialing.

## Fetch existing recordings

Download WAV recordings from WXCC using the search + captures APIs:

```bash
export WXCC_ACCESS_TOKEN="YOUR_LONG_TOKEN_VALUE"
python src/fetch_wav_files.py \
  --from 1759276800000 \
  --to 1761782400000 \
  --output-dir audio/fetched-recordings
```

Helpful flags:

- `--capture-url-key captures.0.url` to force a specific payload path.
- `--include-segments` to include segment data in capture queries.
- `--dry-run` to list downloads without writing files.
- `--max-tasks 5` to limit processed interactions.

## Upload a WAV manually

If you want to generate a public URL without running the main workflow:

```bash
python src/upload_wav_to_s3.py audio/example.wav --profile your-aws-profile
```

## Project layout

- `src/main.py` orchestration entry point.
- `src/upload_wav_to_s3.py` standalone uploader.
- `src/fetch_wav_files.py` WXCC recording downloader.
- `src/FakeAgent/` Playwright automation for agent desktop.
- `src/audioProcessor/` optional audio utilities (ffmpeg required).
- `config/config.json` runtime configuration loaded into environment variables.

## Tests

```bash
python -m unittest tests/test_telephony.py
```

## Known limitations

- Parallel agent dialing is not supported yet. Adding DTMF routing plus contact-center configuration is required to fan out calls safely.
