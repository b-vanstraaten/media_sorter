# Homebrew Setup - Next Steps

## Files Created

- `homebrew-media-sorter-formula.rb` — The Homebrew formula (with SHA256 already filled in)
- `homebrew-tap-README.md` — README for the tap repository

## Step-by-Step Instructions

### 1. Create the Homebrew Tap Repository on GitHub

1. Go to https://github.com/new
2. Create a new repository:
   - **Name:** `homebrew-media-sorter`
   - **Description:** `Homebrew tap for media-sorter`
   - **Public:** Yes
   - **Initialize with README:** Yes

### 2. Clone and Set Up Locally

```bash
# Clone the new tap repo
git clone https://github.com/YOUR_USERNAME/homebrew-media-sorter.git
cd homebrew-media-sorter

# Create the Formula directory
mkdir -p Formula

# Copy the formula file from media-sorter
cp ../media_sorter.packaging/homebrew-media-sorter-formula.rb Formula/media-sorter.rb

# Copy the README
cp ../media_sorter.packaging/homebrew-tap-README.md README.md
```

### 3. Test the Formula Locally

```bash
# From inside the homebrew-media-sorter directory
brew install ./Formula/media-sorter.rb --verbose

# Verify it works
media-sorter --help

# Run the test
brew test media-sorter

# Uninstall after testing
brew uninstall media-sorter
```

### 4. Push to GitHub

```bash
cd homebrew-media-sorter

# Update the README if needed, then commit
git add Formula/ README.md
git commit -m "Add media-sorter formula"
git push origin main
```

### 5. Users Can Now Install

```bash
brew tap YOUR_USERNAME/media-sorter
brew install media-sorter
```

## Troubleshooting

- **Formula fails to install:** Make sure Python 3.12 is available (`brew install python@3.12`)
- **"Class already defined" error:** Uninstall any existing media-sorter first
- **Wrong GitHub username:** Update the `homepage` and `url` in the formula

## Updating for Future Releases

When you release v0.2.0:

1. Update `version` in `pyproject.toml`
2. Create git tag: `git tag v0.2.0 && git push origin v0.2.0`
3. Get new SHA256: `curl -sL https://github.com/YOUR_USERNAME/media-sorter/archive/refs/tags/v0.2.0.tar.gz | shasum -a 256`
4. Update `url` and `sha256` in `Formula/media-sorter.rb`
5. Push the updated formula to the tap repo
