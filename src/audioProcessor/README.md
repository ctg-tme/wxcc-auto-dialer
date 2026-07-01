# Audio Processor

A collection of audio processing utilities for working with audio files.

## Tools

### Stereo Splitter

The `stereoSplitter.py` utility splits stereo WAV files into separate mono files (left and right channels).

#### Requirements

- Python 3.6+
- FFmpeg (must be installed and available in your PATH)

#### Usage

From the command line:

```bash
py stereoSplitter.py input_file.wav [--output-prefix PREFIX]
```

As a module in your Python code:

```python
from audioProcessor.stereoSplitter import split_stereo_to_mono

left_file, right_file = split_stereo_to_mono("input_file.wav", "output_prefix")
```

#### Parameters

- `input_file`: Path to the stereo WAV file
- `-o`, `--output-prefix` (optional): Prefix for the output files. If not provided, uses the input filename

#### Output

The utility creates two mono WAV files:
- `{prefix}_left.wav`: Contains only the left channel
- `{prefix}_right.wav`: Contains only the right channel
