# Subtitle Translator

## Introduction

A Python-based asynchronous subtitle translation tool designed to help users translate subtitle files from one language to another. The tool supports batch translation, context-aware translation, translation quality assessment, and includes a caching mechanism to improve translation efficiency.

## Features

- **Batch Translation**: Supports translating subtitle files in chunks for improved efficiency.
- **Context-Aware Translation**: Includes context information during translation for better accuracy.
- **Quality Assessment**: Uses LLM (like ChatGPT) to evaluate translation quality and provide improvement suggestions.
- **Caching Mechanism**: Caches translation results to avoid repeated translations.
- **Punctuation Handling**: Supports automatic removal of ending punctuation in subtitles (optional).
- **Concurrency Control**: Manages concurrent translation tasks to prevent resource exhaustion.

## Installation

### Prerequisites

- Python 3.7 or higher
- Standard libraries: `asyncio`, `re`, `pathlib`, `subprocess`, `logging`
- `guru` [CLI tool](https://github.com/shafreeck/guru) (for LLM interaction)

### Setup

1. Clone or download this repository.
2. Ensure Python 3.7+ is installed.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Install the `guru` [CLI tool](https://github.com/shafreeck/guru) (refer to `guru`'s official documentation).

## Usage

### Command Line Arguments

```bash
python subtitle_translator.py <input_file> <output_file> [options]
```

- `input_file`: Input subtitle file path (supports `.srt` format).
- `output_file`: Output subtitle file path.
- `--chunk-size`: Number of subtitles per translation batch (default: 30).
- `--max-concurrent`: Maximum concurrent translations (default: 10).
- `--context-size`: Number of context subtitles to include (default: 0).
- `--split-retry`: Split task after N retries (default: 1).
- `--keep-punctuation`: Keep ending punctuation in subtitles (default: false).

### Example

```bash
python subtitle_translator.py input.srt output.srt --chunk-size 20 --max-concurrent 5 --context-size 3
```

### Output

Translation results are saved to the specified output file. The program displays real-time progress and quality assessment results.

## Configuration

The tool is configured through command-line arguments, no additional configuration files needed.

## Important Notes

1. **Translation Quality**: Quality depends on the LLM (e.g., ChatGPT) being used. Manual review is recommended.
2. **Caching**: Results are cached in `.translate_cache` directory. Delete cache files to force retranslation.
3. **Concurrency**: Set `--max-concurrent` according to system resources to prevent overload.

## Troubleshooting

### 1. Unexpected Translation Results

- **Cause**: Insufficient context or LLM quality variation.
- **Solution**: Try increasing `--context-size` or manually adjust translations.

### 2. Slow Translation Speed

- **Cause**: Low concurrency settings or network latency.
- **Solution**: Increase `--max-concurrent` or check network connection.

### 3. Large Cache Files

- **Cause**: Cache accumulation over time.
- **Solution**: Periodically clean the `.translate_cache` directory.

## Contributing

Issues and Pull Requests are welcome to improve this tool.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

**Note**: This tool relies on third-party LLM services (like ChatGPT). Please comply with their terms of service and privacy policies.
