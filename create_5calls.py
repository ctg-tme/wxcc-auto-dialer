#!/usr/bin/env python3
import json

# File sizes from earlier analysis
sizes = {
    "7ca054f5": 4602938, "0147b72b": 4303418, "53f6e242": 4092858, "91cdaad2": 3775098,
    "36ff7101": 2272698, "5d4dcc82": 2220858, "3e9a3afe": 2161018, "5fe4a6c1": 2115898,
    "08a82b6b": 2059258, "66b63a74": 2022778, "6ecc0907": 2014458, "e5247a3a": 2001018,
    "5ca9220d": 1926778, "3518b3d7": 1902778, "7332c16b": 1825978, "b9f81310": 1822778,
    "2a3efc6e": 1814778, "720972c6": 1785978, "f81e15f7": 1782778, "60d8f246": 1782458,
    "2d13b1fa": 1749818, "3996eaad": 1688058, "5b473316": 1623738, "486752f0": 2274938,
    "70d509a0": 2315898, "382b10a2": 1271418, "29c1c525": 1483258, "2939e4cf": 1387258,
    "30bb4b47": 1418618, "4138613a": 2320058, "1e1c9323": 1484538, "e576fbc6": 1311738,
    "5f6fd2b5": 741178, "2e715d1f": 869498, "ad703780": 670778, "9ec14529": 1222778,
    "2be2f952": 700538, "69124f48": 1438458, "2ce7a156": 1433978, "177092b0": 1261498,
    "291e739b": 1218298, "aa193b0f": 1328378, "2c1687bc": 945978, "0132b8ca": 975738,
}

# Load current config
with open("config/config.json", "r") as f:
    config = json.load(f)

# Collect files per agent with full entry template
agent_files = {}
agent_template = {}
for a in config["AGENT_AUDIO_ASSIGNMENTS"]:
    email = a["agent"]["email"]
    agent_id = email.split("+")[1].split("@")[0]
    file_path = a["audio_wav_files"][0]
    file_id = file_path.split("/")[-1][:8]
    if agent_id not in agent_files:
        agent_files[agent_id] = {}
        agent_template[agent_id] = a["agent"].copy()  # Store agent info as template
    agent_files[agent_id][file_id] = file_path

# Agent names mapping
names = {
    "eu2ag1": "Kevin Woo",
    "eu2ag2": "Darren Owens", 
    "eu2ag3": "Emily Nakagawa",
    "eu2ag5": "Sonali Pritchard",
    "eu2ag6": "Murad Higgins",
}

# Find longest per agent and build new assignments
new_assignments = []
order = ["eu2ag5", "eu2ag3", "eu2ag2", "eu2ag6", "eu2ag1"]

print("=" * 60)
print("LONGEST CALL PER AGENT (5 CALLS TOTAL)")
print("=" * 60)

total_duration = 0
for aid in order:
    files = agent_files.get(aid, {})
    longest_id = max(files.keys(), key=lambda f: sizes.get(f, 0))
    longest_path = files[longest_id]
    dur_sec = sizes.get(longest_id, 0) / 16000
    total_duration += dur_sec
    dur = f"{int(dur_sec//60)}:{int(dur_sec%60):02d}"
    
    print(f"{names[aid]:20} | {longest_id} | {dur}")
    
    new_assignments.append({
        "agent": agent_template[aid],
        "audio_wav_files": [longest_path]
    })

print("=" * 60)
print(f"{'TOTAL':20} | 5 calls  | {int(total_duration//60)}:{int(total_duration%60):02d}")
print("=" * 60)

# Build new config preserving all existing keys
new_config = {}
for key in config:
    if key != "AGENT_AUDIO_ASSIGNMENTS":
        new_config[key] = config[key]
new_config["AGENT_AUDIO_ASSIGNMENTS"] = new_assignments

# Write new config
with open("config/config.json", "w") as f:
    json.dump(new_config, f, indent=2)

print("\n✅ config/config.json updated with 5 calls (1 per agent)")
