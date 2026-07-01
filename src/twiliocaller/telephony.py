# src/twiliocaller/telephony.py
import os
import time
from twilio.rest import Client

TERMINAL_STATUSES = {"completed", "busy", "failed", "no-answer", "canceled"}
DEFAULT_CUSTOMER_WAV_URL = os.getenv(
    "DEFAULT_CUSTOMER_WAV_URL",
    "https://liamfrawley.s3.eu-north-1.amazonaws.com/bicycleSpecialist_left.wav",
)
DEFAULT_CUSTOMER_WAV_DELAY = float(os.getenv("CUSTOMER_AUDIO_DELAY_SECONDS", "0.8"))

def _build_client():
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    if not account_sid or not auth_token:
        raise ValueError("Twilio credentials are not set in the environment variables.")
    return Client(account_sid, auth_token)

def _build_twiml(wav_url: str, delay_seconds: float) -> str:
    pause_fragment = ""
    if delay_seconds and delay_seconds > 0:
        pause_fragment = f'<Pause length="{delay_seconds}"/>'
    return (
        '<Response>'
        f"{pause_fragment}"
        f"<Play>{wav_url}</Play>"
        '</Response>'
    )

def make_call(to_number, wav_url=None, delay_seconds=DEFAULT_CUSTOMER_WAV_DELAY):
    client = _build_client()
    from_number = os.getenv('TWILIO_PHONE_NUMBER')
    audio_url = wav_url or DEFAULT_CUSTOMER_WAV_URL
    call = client.calls.create(
        to=to_number,
        from_=from_number,
        twiml=_build_twiml(audio_url, delay_seconds),
    )
    print(f"Call initiated. SID: {call.sid}")
    return call.sid

def wait_for_call_status(sid, desired_statuses=("in-progress",), timeout_seconds=45, poll_interval=2):
    """Poll Twilio for the call status until it matches a desired value or reaches a terminal state."""
    client = _build_client()
    deadline = time.time() + timeout_seconds
    last_status = None
    print(f"[Twilio] Waiting for call {sid} to reach status: {desired_statuses}")
    while time.time() < deadline:
        call = client.calls(sid).fetch()
        last_status = call.status
        print(f"[Twilio] Call {sid} status: {last_status}")
        if last_status in desired_statuses:
            print(f"[Twilio] Call {sid} reached desired status: {last_status}")
            return last_status
        if last_status in TERMINAL_STATUSES:
            print(f"[Twilio] Call {sid} reached terminal status: {last_status}")
            return last_status
        time.sleep(poll_interval)
    print(f"[Twilio] Timeout waiting for call {sid}. Last status: {last_status}")
    return last_status
