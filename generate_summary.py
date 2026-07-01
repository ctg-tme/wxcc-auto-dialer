#!/usr/bin/env python3
import json

with open("config/config.json", "r") as f:
    config = json.load(f)

assignments = config["AGENT_AUDIO_ASSIGNMENTS"]

agent_names = {
    "eu2ag1": "Kevin Woo",
    "eu2ag2": "Darren Owens", 
    "eu2ag3": "Emily Nakagawa",
    "eu2ag5": "Sonali Pritchard",
    "eu2ag6": "Murad Higgins"
}

wav_data = {
    "0132b8ca": {"size": 975738, "prof": "Needs Improvement", "eng": "Standard", "sent": "Somewhat Satisfied"},
    "0147b72b": {"size": 4303418, "prof": "Exceptional", "eng": "Highly Engaged", "sent": "Very Frustrated"},
    "08a82b6b": {"size": 2059258, "prof": "Exceptional", "eng": "Engaged", "sent": "Satisfied"},
    "177092b0": {"size": 1261498, "prof": "Needs Improvement", "eng": "Dismissive", "sent": "Frustrated"},
    "1e1c9323": {"size": 1484538, "prof": "Standard", "eng": "Engaged", "sent": "Neutral"},
    "291e739b": {"size": 1218298, "prof": "Unprofessional", "eng": "Dismissive", "sent": "Neutral"},
    "2939e4cf": {"size": 1387258, "prof": "Exceptional", "eng": "Highly Engaged", "sent": "Satisfied"},
    "29c1c525": {"size": 1483258, "prof": "Exceptional", "eng": "Standard", "sent": "Satisfied"},
    "2a3efc6e": {"size": 1814778, "prof": "Exceptional", "eng": "Engaged", "sent": "Very Happy"},
    "2be2f952": {"size": 700538, "prof": "Highly Professional", "eng": "Engaged", "sent": "Satisfied"},
    "2c1687bc": {"size": 945978, "prof": "Needs Improvement", "eng": "Standard", "sent": "Somewhat Satisfied"},
    "2ce7a156": {"size": 1433978, "prof": "Unprofessional", "eng": "Dismissive", "sent": "Neutral"},
    "2d13b1fa": {"size": 1749818, "prof": "Highly Professional", "eng": "Standard", "sent": "Somewhat Satisfied"},
    "2e715d1f": {"size": 869498, "prof": "Highly Professional", "eng": "Standard", "sent": "Satisfied"},
    "30bb4b47": {"size": 1418618, "prof": "Exceptional", "eng": "Highly Engaged", "sent": "Satisfied"},
    "3518b3d7": {"size": 1902778, "prof": "Exceptional", "eng": "Engaged", "sent": "Very Happy"},
    "36ff7101": {"size": 2272698, "prof": "Exceptional", "eng": "Exceptional", "sent": "Very Happy"},
    "382b10a2": {"size": 1271418, "prof": "Exceptional", "eng": "Engaged", "sent": "Satisfied"},
    "3996eaad": {"size": 1688058, "prof": "Exceptional", "eng": "Standard", "sent": "Satisfied"},
    "3e9a3afe": {"size": 2161018, "prof": "Exceptional", "eng": "Engaged", "sent": "Satisfied"},
    "4138613a": {"size": 2320058, "prof": "Standard", "eng": "Low Engagement", "sent": "Satisfied"},
    "486752f0": {"size": 2274938, "prof": "Exceptional", "eng": "Engaged", "sent": "Satisfied"},
    "53f6e242": {"size": 4092858, "prof": "Exceptional", "eng": "Highly Engaged", "sent": "Frustrated"},
    "5b473316": {"size": 1623738, "prof": "Exceptional", "eng": "Engaged", "sent": "Satisfied"},
    "5ca9220d": {"size": 1926778, "prof": "Exceptional", "eng": "Highly Engaged", "sent": "Very Happy"},
    "5d4dcc82": {"size": 2220858, "prof": "Exceptional", "eng": "Engaged", "sent": "Very Happy"},
    "5f6fd2b5": {"size": 741178, "prof": "Standard", "eng": "Standard", "sent": "Somewhat Satisfied"},
    "5fe4a6c1": {"size": 2115898, "prof": "Exceptional", "eng": "Engaged", "sent": "Satisfied"},
    "60d8f246": {"size": 1782458, "prof": "Exceptional", "eng": "Standard", "sent": "Satisfied"},
    "66b63a74": {"size": 2022778, "prof": "Exceptional", "eng": "Highly Engaged", "sent": "Satisfied"},
    "69124f48": {"size": 1438458, "prof": "Highly Professional", "eng": "Standard", "sent": "Satisfied"},
    "6ecc0907": {"size": 2014458, "prof": "Exceptional", "eng": "Highly Engaged", "sent": "Satisfied"},
    "70d509a0": {"size": 2315898, "prof": "Exceptional", "eng": "Engaged", "sent": "Very Happy"},
    "720972c6": {"size": 1785978, "prof": "Exceptional", "eng": "Engaged", "sent": "Very Happy"},
    "7332c16b": {"size": 1825978, "prof": "Highly Professional", "eng": "Standard", "sent": "Neutral"},
    "7ca054f5": {"size": 4602938, "prof": "Exceptional", "eng": "Highly Engaged", "sent": "Somewhat Satisfied"},
    "91cdaad2": {"size": 3775098, "prof": "Exceptional", "eng": "Standard", "sent": "Satisfied"},
    "9ec14529": {"size": 1222778, "prof": "Highly Professional", "eng": "Engaged", "sent": "Frustrated"},
    "aa193b0f": {"size": 1328378, "prof": "Needs Improvement", "eng": "Standard", "sent": "Somewhat Satisfied"},
    "ad703780": {"size": 670778, "prof": "Highly Professional", "eng": "Engaged", "sent": "Satisfied"},
    "b9f81310": {"size": 1822778, "prof": "Needs Improvement", "eng": "Standard", "sent": "Somewhat Satisfied"},
    "e5247a3a": {"size": 2001018, "prof": "Needs Improvement", "eng": "Standard", "sent": "Neutral"},
    "e576fbc6": {"size": 1311738, "prof": "Standard", "eng": "Dismissive", "sent": "Somewhat Satisfied"},
    "f81e15f7": {"size": 1782778, "prof": "Highly Professional", "eng": "Standard", "sent": "Somewhat Satisfied"},
}

agent_category = {
    "eu2ag1": "Unprofessional",
    "eu2ag2": "Highly Professional",
    "eu2ag3": "Longest Calls",
    "eu2ag5": "Standard",
    "eu2ag6": "Exceptional"
}

stats = {}
for a in assignments:
    email = a["agent"]["email"]
    agent_id = email.split("+")[1].split("@")[0]
    wav = a["audio_wav_files"][0].split("/")[-1][:8]
    if agent_id not in stats:
        stats[agent_id] = {"calls": 0, "files": [], "sizes": [], "sents": [], "engs": []}
    stats[agent_id]["calls"] += 1
    stats[agent_id]["files"].append(wav)
    if wav in wav_data:
        stats[agent_id]["sizes"].append(wav_data[wav]["size"])
        stats[agent_id]["sents"].append(wav_data[wav]["sent"])
        stats[agent_id]["engs"].append(wav_data[wav]["eng"])

def bytes_to_duration(size):
    # WAV: 8000 Hz, ulaw, 2 bytes/frame = 16000 bytes/sec
    return size / 16000

def format_duration(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"

def most_common(lst):
    from collections import Counter
    return Counter(lst).most_common(1)[0][0] if lst else "N/A"

print("=" * 120)
print("AGENT SUMMARY TABLE")
print("=" * 120)
print(f"{'Agent':<20} {'Email':<35} {'Calls':>6} {'Avg Dur':>10} {'Customer Satisfaction':<22} {'Agent Engagement':<18} {'Category':<20}")
print("-" * 120)

for aid in ["eu2ag5", "eu2ag3", "eu2ag2", "eu2ag6", "eu2ag1"]:
    s = stats.get(aid, {"calls": 0, "sizes": [], "sents": [], "engs": []})
    name = agent_names[aid]
    email = f"agent+{aid}@example.com"
    calls = s["calls"]
    avg_dur = format_duration(bytes_to_duration(sum(s["sizes"]) / calls)) if calls > 0 and s["sizes"] else "0:00"
    sat = most_common(s["sents"])
    eng = most_common(s["engs"])
    cat = agent_category[aid]
    print(f"{name:<20} {email:<35} {calls:>6} {avg_dur:>10} {sat:<22} {eng:<18} {cat:<20}")

print("-" * 120)
print(f"TOTAL CALLS: {len(assignments)}")
print()

# Detailed call list
print("=" * 140)
print("DETAILED CALL LIST (Execution Order)")
print("=" * 140)
print(f"{'#':>4} {'Agent':<20} {'Email':<35} {'WAV File':<45} {'Duration':>10} {'Satisfaction':<18}")
print("-" * 140)

for i, a in enumerate(assignments, 1):
    email = a["agent"]["email"]
    agent_id = email.split("+")[1].split("@")[0]
    name = agent_names[agent_id]
    wav = a["audio_wav_files"][0]
    file_id = wav.split("/")[-1][:8]
    
    if file_id in wav_data:
        dur = format_duration(bytes_to_duration(wav_data[file_id]["size"]))
        sat = wav_data[file_id]["sent"]
    else:
        dur = "N/A"
        sat = "N/A"
    
    print(f"{i:>4} {name:<20} {email:<35} {wav:<45} {dur:>10} {sat:<18}")

print("-" * 140)
