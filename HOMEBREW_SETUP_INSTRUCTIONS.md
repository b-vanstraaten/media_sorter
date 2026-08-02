# Homebrew Setup - Next Steps

## Files Created

- `homebrew-marquee-formula.rb` — The Homebrew formula (with SHA256 already filled in)
- `homebrew-tap-README.md` — README for the tap repository

## Step-by-Step Instructions

### 1. Create the Homebrew Tap Repository on GitHub

1. Go to https://github.com/new
2. Create a new repository:
   - **Name:** `homebrew-marquee`
   - **Description:** `Homebrew tap for marquee`
   - **Public:** Yes
   - **Initialize with README:** Yes

### 2. Clone and Set Up Locally

```bash
# Clone the new tap repo
git clone https://github.com/b-vanstraaten/homebrew-marquee.git
cd homebrew-marquee

# Create the Formula directory
mkdir -p Formula

# Copy the formula file from marquee
cp ../marquee/homebrew-marquee-formula.rb Formula/marquee.rb

# Copy the README
cp ../marquee/homebrew-tap-README.md README.md
```

### 3. Test the Formula Locally

Recent Homebrew versions refuse to install a bare formula file directly --
it has to live in a tap. Easiest way to test before pushing:

```bash
brew tap-new local/marquee-test --no-git
cp Formula/marquee.rb "$(brew --repository)/Library/Taps/local/homebrew-marquee-test/Formula/marquee.rb"

brew install --build-from-source --verbose local/marquee-test/marquee

# Verify it works
marquee --help
brew test local/marquee-test/marquee

# Clean up
brew uninstall local/marquee-test/marquee
brew untap local/marquee-test
```

### 4. Push to GitHub

```bash
cd homebrew-marquee

# Update the README if needed, then commit
git add Formula/ README.md
git commit -m "Add marquee formula"
git push origin main
```

### 5. Users Can Now Install

```bash
brew tap b-vanstraaten/marquee
brew trust b-vanstraaten/marquee   # required once: Homebrew won't load formulae from third-party taps otherwise
brew install marquee
```

## Troubleshooting

- **Formula fails to install:** Make sure Python 3.12 is available (`brew install python@3.12`)
- **"Class already defined" error:** Uninstall any existing marquee first
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
   `curl -sL https://github.com/b-vanstraaten/marquee/archive/refs/tags/vX.Y.Z.tar.gz | shasum -a 256`
5. Update `url` and `sha256` (the formula's top-level ones, not a resource)
   in `Formula/marquee.rb`.
6. Test locally with the tap steps above, then push the updated formula to
   the tap repo.
