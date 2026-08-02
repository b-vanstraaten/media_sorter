# homebrew-marquee

Homebrew tap for [marquee](https://github.com/b-vanstraaten/media_sorter).

## Installation

```bash
brew tap b-vanstraaten/marquee
brew trust b-vanstraaten/marquee   # required once: Homebrew won't load formulae from third-party taps otherwise
brew install marquee
```

## Usage

```bash
marquee --source ~/Downloads --output ~/Media --model llama3.2 --dry-run
```

See the [main repository](https://github.com/b-vanstraaten/media_sorter) for full documentation.
