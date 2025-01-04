# Subtitle Translator Tool

## Introduction

This is an asynchronous subtitle translation tool based on Python, designed to help users translate subtitle files from one language to another. The tool supports batch translation, context-aware translation, translation quality evaluation, and provides a caching mechanism to improve translation efficiency.

## Features

- **Batch Translation**: Supports translating subtitle files in chunks to improve efficiency.
- **Context-Aware Translation**: Includes context information during translation to enhance accuracy.
- **Translation Quality Evaluation**: Uses LLMs (such as ChatGPT) to evaluate the quality of translations and provide revision suggestions.
- **Caching Mechanism**: Supports caching of translation results to avoid redundant translations of the same content.
- **Punctuation Handling**: Optionally removes punctuation at the end of subtitles.
- **Concurrency Control**: Allows control over the number of concurrent translation tasks to prevent resource exhaustion.

## Installation

### Dependencies

- Python 3.7 or higher
- Standard libraries such as `asyncio`, `re`, `pathlib`, `subprocess`, and `logging`
- `guru` [command-line tool](https://github.com/shafreeck/guru) (for interacting with LLMs)

### Installation Steps

1. Clone or download this repository to your local machine.
2. Ensure Python 3.7 or higher is installed.
3. Install the `guru` [command-line tool](https://github.com/shafreeck/guru) (refer to the official `guru` documentation for installation instructions).

## Usage

### Command-Line Arguments

```bash
python subtitle_translator.py <input_file> <output_file> [options]
```

- `input_file`: Path to the input subtitle file (supports `.srt` format).
- `output_file`: Path to the output subtitle file.
- `--chunk-size`: Number of subtitles to translate at a time (default: 30).
- `--max-concurrent`: Maximum number of concurrent tasks (default: 10).
- `--context-size`: Number of contextual subtitles to include during translation (default: 0).
- `--split-retry`: Split tasks after every N retries (default: 1).
- `--keep-punctuation`: Retain punctuation at the end of subtitles (default is to remove it).

### Example

```bash
python subtitle_translator.py input.srt output.srt --chunk-size 20 --max-concurrent 5 --context-size 3
```

### Output

After translation, the results will be saved to the specified output file. The program will display real-time progress and quality evaluation results.

## Configuration File

This tool is configured via command-line arguments and does not require an additional configuration file.

## Notes

1. **Translation Quality**: The quality of translation depends on the performance of the LLM (e.g., ChatGPT) used. It is recommended to manually review the translation results before use.
2. **Caching Mechanism**: Translation results are cached in the `.translate_cache` directory to avoid redundant translations. If re-translation is needed, manually delete the cache files.
3. **Concurrency Control**: Set the `--max-concurrent` parameter appropriately based on system resources to avoid resource exhaustion.

## Frequently Asked Questions (FAQ)

### 1. Translation Results Are Not as Expected

- **Reason**: This may be due to insufficient context or unstable translation quality from the LLM.
- **Solution**: Try increasing the `--context-size` parameter or manually adjust the translation results.

### 2. Slow Translation Speed

- **Reason**: This may be due to low concurrency settings or network latency.
- **Solution**: Increase the `--max-concurrent` parameter appropriately or check the network connection.

### 3. Large Cache Files

- **Reason**: Cache files may occupy significant disk space after prolonged use.
- **Solution**: Periodically clean up cache files in the `.translate_cache` directory.

## Contribution

Issues and Pull Requests are welcome to improve this tool.

## License

This project is licensed under the MIT License. For details, please refer to the [LICENSE](LICENSE) file.

---

**Note**: This tool relies on third-party LLM services (e.g., ChatGPT). Please comply with the terms of service and privacy policies of these services when using this tool.
