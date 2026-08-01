# homebrew-media-sorter

Homebrew tap for [media-sorter](https://github.com/b-vanstraaten/media_sorter).

## Installation

```bash
brew tap b-vanstraaten/media-sorter
brew trust b-vanstraaten/media-sorter   # required once: Homebrew won't load formulae from third-party taps otherwise
brew install media-sorter
```

## Usage

```bash
media-sorter --source ~/Downloads --output ~/Media --model llama3.2 --dry-run
```

See the [main repository](https://github.com/b-vanstraaten/media_sorter) for full documentation.
