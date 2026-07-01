# src/main.py
import os
import glob
import json
import asyncio
import random
import shlex
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, cast

from config_loader import load_env_from_json

load_env_from_json()

from datetime import datetime
from playwright.async_api import async_playwright

from FakeAgent.fake_agent import launch_browser
from twiliocaller.telephony import (
    DEFAULT_CUSTOMER_WAV_DELAY,
    make_call,
)
from FakeAgent.availability import set_availability_state
from FakeAgent.answer_call import answer_incoming_call
from FakeAgent.end_call import end_call
from upload_wav_to_s3 import (
    DEFAULT_BUCKET,
    DEFAULT_REGION,
    build_key,
    create_s3_client,
    ensure_wav_file,
    get_wav_duration_seconds,
    split_channels_if_needed,
    upload_wav,
)

NUM_FAKE_CALLS = 1
CUSTOMER_AUDIO_DELAY = DEFAULT_CUSTOMER_WAV_DELAY


def _load_contact_center_number():
    to_number = os.getenv('CONTACT_CENTER_PHONE_NUMBER')
    if not to_number:
        raise ValueError("No phone number provided. Please set the CONTACT_CENTER_PHONE_NUMBER environment variable or provide a number.")
    return to_number


def _parse_wav_inputs(raw_value: Optional[Union[str, List[str]]] = None, *, context_label: str = "AUDIO_WAV_FILES") -> List[str]:
    if raw_value is None:
        raw = os.getenv("AUDIO_WAV_FILES", "")
    elif isinstance(raw_value, str):
        raw = raw_value
    elif isinstance(raw_value, list):
        raw = "\n".join(str(item) for item in raw_value)
    else:
        raise TypeError(f"Unsupported WAV input type for {context_label}: {type(raw_value).__name__}")
    raw = raw or ""
    if not raw.strip():
        if context_label == "AUDIO_WAV_FILES":
            raise ValueError(
                "No WAV files configured. Set AUDIO_WAV_FILES in config/config.json to a list of paths or globs."
            )
        raise ValueError(
            f"No WAV files configured for {context_label}. Provide at least one path (supports shell-style globs)."
        )
    patterns: List[str] = []
    for line in raw.splitlines():
        cleaned = line.replace(",", " ").strip()
        if not cleaned:
            continue
        patterns.extend(shlex.split(cleaned))
    if not patterns:
        raise ValueError(
            f"{context_label} did not contain any usable entries. Provide at least one path (supports shell-style globs)."
        )
    expanded: List[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            expanded.extend(matches)
        else:
            expanded.append(pattern)
    return expanded


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _format_duration_hms(total_seconds: float) -> str:
    total_seconds_int = max(0, int(round(total_seconds)))
    hours, remainder = divmod(total_seconds_int, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


def _format_duration_ms(total_seconds: float) -> str:
    total_seconds_int = max(0, int(round(total_seconds)))
    minutes, seconds = divmod(total_seconds_int, 60)
    return f"{minutes}m {seconds}s"


def _load_agent_assignments_from_env() -> Optional[List[dict]]:
    raw = os.getenv("AGENT_AUDIO_ASSIGNMENTS")
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = []
        for line in raw.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            parsed.append(json.loads(cleaned))
    if isinstance(parsed, dict):
        if "assignments" in parsed:
            parsed = parsed["assignments"]
        elif "agents" in parsed:
            parsed = parsed["agents"]
        else:
            raise ValueError(
                "AGENT_AUDIO_ASSIGNMENTS must be a JSON array (optionally nested under an 'assignments' or 'agents' key)."
            )
    if not isinstance(parsed, list):
        raise ValueError("AGENT_AUDIO_ASSIGNMENTS must be a JSON array of agent assignments.")
    return parsed


def _merge_agent_config(
    overrides: Optional[Dict[str, Optional[str]]],
    context_label: str,
) -> Dict[str, str]:
    if overrides is None:
        raise ValueError(
            f"{context_label} is missing agent configuration. Provide an 'agent' object with email, password, and extension."
        )
    if not isinstance(overrides, dict):
        raise ValueError(f"{context_label}.agent must be an object with agent credentials.")
    merged: Dict[str, Optional[str]] = {k: v for k, v in overrides.items() if v is not None}
    merged["role"] = merged.get("role") or "Agent"
    missing_fields = [key for key in ("email", "password", "extension") if not merged.get(key)]
    if missing_fields:
        raise ValueError(
            f"Missing agent configuration for {', '.join(missing_fields)} in {context_label}. "
            "Provide them on the assignment's agent object."
        )
    return cast(Dict[str, str], merged)


def _load_runtime_settings():
    bucket = os.getenv("S3_BUCKET", DEFAULT_BUCKET)
    region = os.getenv("S3_REGION", DEFAULT_REGION)
    prefix = os.getenv("S3_PREFIX", "audio-uploads/")
    profile = os.getenv("AWS_PROFILE")
    keep_browser_open = _env_flag("KEEP_BROWSER_OPEN", False)
    customer_delay = float(os.getenv("CUSTOMER_AUDIO_DELAY_SECONDS", str(CUSTOMER_AUDIO_DELAY)))
    assignments = _load_agent_assignments_from_env()
    agent_jobs = []
    if assignments is None:
        raise ValueError(
            "AGENT_AUDIO_ASSIGNMENTS is required. Define at least one agent assignment with agent credentials and `audio_wav_files`."
        )
    else:
        if not assignments:
            raise ValueError(
                "AGENT_AUDIO_ASSIGNMENTS was provided but empty. Define at least one agent assignment with `audio_wav_files`."
            )
        assignments_in_random_order = list(assignments)
        random.shuffle(assignments_in_random_order)
        for idx, assignment in enumerate(assignments_in_random_order):
            context_label = f"AGENT_AUDIO_ASSIGNMENTS[{idx}]"
            if not isinstance(assignment, dict):
                raise ValueError(f"{context_label} must be an object describing the agent and its audio files.")
            raw_agent = assignment.get("agent")
            if raw_agent is None:
                raw_agent = {
                    key: value
                    for key, value in assignment.items()
                    if key not in {"audio_wav_files", "audio_files", "wav_files"}
                }
            wav_value = (
                assignment.get("audio_wav_files")
                or assignment.get("audio_files")
                or assignment.get("wav_files")
            )
            if wav_value is None:
                raise ValueError(f"{context_label} is missing 'audio_wav_files'.")
            wav_files = _parse_wav_inputs(
                wav_value,
                context_label=f"{context_label}.audio_wav_files",
            )
            agent_jobs.append(
                {
                    "agent_config": _merge_agent_config(raw_agent, context_label),
                    "wav_files": wav_files,
                }
            )
    return {
        "agent_jobs": agent_jobs,
        "bucket": bucket,
        "region": region,
        "prefix": prefix,
        "profile": profile,
        "keep_browser_open": keep_browser_open,
        "customer_delay": customer_delay,
    }


def _prepare_audio_jobs(
    file_args: List[str],
    bucket: str,
    region: str,
    prefix: Optional[str],
    profile: Optional[str],
) -> List[dict]:
    """Split/upload WAV files and return metadata for orchestration."""
    if not file_args:
        return []
    client = create_s3_client(region, profile)
    jobs: List[dict] = []
    for raw_path in file_args:
        source = Path(raw_path).expanduser().resolve()
        ensure_wav_file(source)
        duration_seconds = get_wav_duration_seconds(source)
        upload_source, agent_channel = split_channels_if_needed(source)
        agent_audio = agent_channel or upload_source
        key = build_key(upload_source, provided_key=None, prefix=prefix)
        print(f"[audio] Uploading customer channel for {upload_source.name} to s3://{bucket}/{key}")
        public_url = upload_wav(upload_source, bucket, key, client)
        print(f"[audio] Customer audio available at {public_url}")
        jobs.append(
            {
                "source": source,
                "customer_wav_url": public_url,
                "agent_audio_file": str(agent_audio),
                "duration_seconds": duration_seconds,
            }
        )
    return jobs


def _stage_agent_audio(source_path: Path, destination_path: Path) -> None:
    """Copy the agent channel into the path used by Playwright for fake audio."""
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source_path, destination_path)

async def orchestrate(user_config, audio_jobs, customer_delay, keep_browser_open=False):
    if not audio_jobs:
        print("[main.py] No audio jobs to orchestrate.")
        return {"calls_completed": 0, "call_time_seconds": 0.0}
    calls_completed = 0
    call_time_seconds = 0.0
    to_number = _load_contact_center_number()
    ready_for_call_event = asyncio.Event()
    call_answered_event = asyncio.Event()
    staged_audio_path = Path(user_config["audio_file"]).expanduser()
    first_agent_source = Path(audio_jobs[0]["agent_audio_file"]).expanduser()
    _stage_agent_audio(first_agent_source, staged_audio_path)
    print(f"[main.py] Logging in agent {user_config['email']} and waiting for available state...")
    async with async_playwright() as playwright:
        context, page = await launch_browser(playwright, user_config, ready_for_call_event, call_answered_event)
        call_counter = 0
        total_jobs = len(audio_jobs)
        for job_index, job in enumerate(audio_jobs):
            print(
                f"[main.py] Starting orchestration for {job['source'].name} -> {job['customer_wav_url']}"
            )
            _stage_agent_audio(Path(job["agent_audio_file"]).expanduser(), staged_audio_path)
            # subtract 1 here because the call should be ended slightly before the audio finishes to
            # ensure the call ends on the agentx desktop side 
            call_duration = job["duration_seconds"] - 1
            abort_runs = False
            for i in range(NUM_FAKE_CALLS):
                call_counter += 1
                print(
                    f"[main.py] Fake call {call_counter} "
                    f"(job {job_index + 1}/{total_jobs}, iteration {i + 1}/{NUM_FAKE_CALLS}) "
                    f"started for {user_config['email']}"
                )
                availability = await set_availability_state(page, user_config, 0)
                if availability == "engaged":
                    print(f"[main.py] Agent {user_config['email']} is engaged. Ending call loop.")
                    await end_call(page)
                    abort_runs = True
                    break
                print(f"[main.py] Agent {user_config['email']} set to available for call {i+1}")
                call_id = make_call(to_number, wav_url=job["customer_wav_url"], delay_seconds=customer_delay)
                calls_completed += 1
                call_time_seconds += max(0.0, call_duration)
                print(f"[main.py] Customer call {i+1} triggered. Waiting for agent {user_config['email']} to answer...")
                await answer_incoming_call(page)
                print(f"[main.py] Agent {user_config['email']} answered call {i+1} at {datetime.now().isoformat()}")
                print(
                    f"[main.py] Waiting {_format_duration_ms(call_duration)} "
                    "for audio to finish before ending the call."
                )
                await asyncio.sleep(call_duration)
                await end_call(page)
                print(
                    f"[main.py] Call {call_counter} ended for {user_config['email']}. "
                    "Waiting 10s before next call..."
                )
                await asyncio.sleep(10)
            if abort_runs:
                break
        print(f"[main.py] All fake calls completed for {user_config['email']}.")
        if keep_browser_open:
            print(f"[main.py] Leaving browser open for {user_config['email']}. Press Ctrl+C to exit.")
            await asyncio.Event().wait()

    return {"calls_completed": calls_completed, "call_time_seconds": call_time_seconds}


if __name__ == "__main__":
    run_started_at = datetime.now()
    run_started_monotonic = time.monotonic()
    print(f"[main.py] Run started at {run_started_at.isoformat()}")
    settings = _load_runtime_settings()
    staged_agent_audio = Path("audio") / "split-files" / "current_agent_input.wav"
    agent_jobs = settings["agent_jobs"]
    if not agent_jobs:
        raise RuntimeError("No agents configured. Provide AGENT_AUDIO_ASSIGNMENTS entries.")

    total_agents = len(agent_jobs)
    total_calls = 0
    total_call_time_seconds = 0.0
    calls_per_agent = []
    for agent_index, agent_job in enumerate(agent_jobs, start=1):
        agent_config = {**agent_job["agent_config"], "audio_file": str(staged_agent_audio)}
        agent_audio_jobs = _prepare_audio_jobs(
            agent_job["wav_files"],
            bucket=settings["bucket"],
            region=settings["region"],
            prefix=settings["prefix"],
            profile=settings["profile"],
        )
        if not agent_audio_jobs:
            print(
                f"[main.py] No audio jobs were prepared for agent assignment {agent_index}/{total_agents}. Skipping."
            )
            calls_per_agent.append({"email": agent_config["email"], "calls": 0})
            continue
        keep_browser_open = settings["keep_browser_open"] and agent_index == total_agents
        print(
            f"[main.py] === Starting agent run {agent_index}/{total_agents} for {agent_config['email']} "
            f"({len(agent_audio_jobs)} audio file(s)) ==="
        )
        run_result = asyncio.run(
            orchestrate(
                agent_config,
                audio_jobs=agent_audio_jobs,
                customer_delay=settings["customer_delay"],
                keep_browser_open=keep_browser_open,
            )
        )
        calls_completed = run_result["calls_completed"]
        total_calls += calls_completed
        total_call_time_seconds += run_result["call_time_seconds"]
        calls_per_agent.append({"email": agent_config["email"], "calls": calls_completed})

    run_finished_at = datetime.now()
    print(f"[main.py] Run finished at {run_finished_at.isoformat()}")
    total_duration_seconds = time.monotonic() - run_started_monotonic
    total_setup_time_seconds = max(0.0, total_duration_seconds - total_call_time_seconds)
    calls_per_agent_summary = ", ".join(
        f"{entry['email']}={entry['calls']}" for entry in calls_per_agent
    ) or "none"
    print("[main.py] === Summary ===")
    print(f"[main.py] Agents: {total_agents}")
    print(f"[main.py] Calls: {total_calls}")
    print(f"[main.py] Calls per agent: {calls_per_agent_summary}")
    print(f"[main.py] Total call time: {_format_duration_hms(total_call_time_seconds)}")
    print(f"[main.py] Total setup time: {_format_duration_hms(total_setup_time_seconds)}")
    print(f"[main.py] Total duration: {_format_duration_hms(total_duration_seconds)}")
