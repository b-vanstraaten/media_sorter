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
git clone https://github.com/b-vanstraaten/homebrew-media-sorter.git
cd homebrew-media-sorter

# Create the Formula directory
mkdir -p Formula

# Copy the formula file from media_sorter
cp ../media_sorter/homebrew-media-sorter-formula.rb Formula/media-sorter.rb

# Copy the README
cp ../media_sorter/homebrew-tap-README.md README.md
```

### 3. Test the Formula Locally

Recent Homebrew versions refuse to install a bare formula file directly --
it has to live in a tap. Easiest way to test before pushing:

```bash
brew tap-new local/media-sorter-test --no-git
cp Formula/media-sorter.rb "$(brew --repository)/Library/Taps/local/homebrew-media-sorter-test/Formula/media-sorter.rb"

brew install --build-from-source --verbose local/media-sorter-test/media-sorter

# Verify it works
media-sorter --help
brew test local/media-sorter-test/media-sorter

# Clean up
brew uninstall local/media-sorter-test/media-sorter
brew untap local/media-sorter-test
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
brew tap b-vanstraaten/media-sorter
brew trust b-vanstraaten/media-sorter   # required once: Homebrew won't load formulae from third-party taps otherwise
brew install media-sorter
```

## Troubleshooting

- **Formula fails to install:** Make sure Python 3.12 is available (`brew install python@3.12`)
- **"Class already defined" error:** Uninstall any existing media-sorter first
- **Wrong GitHub username:** Update the `homepage` and `url` in the formula

## Updating for Future Releases

The formula vendors every runtime dependency as a pinned `resource` block
(exact version + sha256) instead of letting `pip` resolve them at install
time, so `brew install` never has to reach PyPI. That means two things need
updating in step with each other, not just the version:

1. Update `version` in `pyproject.toml`, run `uv lock` to refresh `uv.lock`.
2. If `ollama` or `rich` (or anything in their dependency tree) moved
   versions since the last release, update the matching `resource` block(s)
   in the formula: fetch the new pure-Python wheel's URL/sha256 from
   `https://pypi.org/pypi/<package>/<version>/json`, or -- for
   `pydantic-core`, the one compiled dependency -- the three platform wheels
   (`macosx_arm64`, `macosx_x86_64`, `manylinux_x86_64`) for the target
   Python's `cp3xx` tag. Keep resources in dependency order (each one before
   anything that depends on it) so installs never need the network.
3. Create git tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
4. Get the release tarball's real SHA256:
   `curl -sL https://github.com/b-vanstraaten/media_sorter/archive/refs/tags/vX.Y.Z.tar.gz | shasum -a 256`
5. Update `url` and `sha256` (the formula's top-level ones, not a resource)
   in `Formula/media-sorter.rb`.
6. Test locally with the tap steps above, then push the updated formula to
   the tap repo.
