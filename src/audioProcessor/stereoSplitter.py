import subprocess
import os
import argparse
from pathlib import Path

def split_stereo_to_mono(input_file, output_prefix=None):
    """
    Split a stereo WAV file into two mono WAV files using FFmpeg.
    
    Args:
        input_file (str): Path to the input stereo WAV file
        output_prefix (str, optional): Prefix for output files. If None, uses the input filename without extension
    
    Returns:
        tuple: Paths to the two output mono files
    """
    # Input validation
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Set output prefix if not provided
    if output_prefix is None:
        output_prefix = Path(input_file).stem
    
    # Define output filenames
    left_channel = f"{output_prefix}_left.wav"
    right_channel = f"{output_prefix}_right.wav"
    
    # Split left channel - using modern channel mapping
    subprocess.run([
        "ffmpeg", "-i", input_file, 
        "-af", "pan=mono|c0=c0", 
        "-c:a", "pcm_s16le", "-y", left_channel
    ], check=True)
    
    # Split right channel - using modern channel mapping
    subprocess.run([
        "ffmpeg", "-i", input_file, 
        "-af", "pan=mono|c0=c1", 
        "-c:a", "pcm_s16le", "-y", right_channel
    ], check=True)
    
    print(f"Successfully split {input_file} into:")
    print(f"Left channel: {left_channel}")
    print(f"Right channel: {right_channel}")
    
    return left_channel, right_channel

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Split stereo WAV file into two mono WAV files')
    parser.add_argument('input_file', help='Path to the input stereo WAV file')
    parser.add_argument('-o', '--output-prefix', help='Prefix for output files')
    
    args = parser.parse_args()
    
    # Call the split function
    try:
        split_stereo_to_mono(args.input_file, args.output_prefix)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())