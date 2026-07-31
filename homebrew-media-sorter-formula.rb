class MediaSorter < Formula
  desc "Sort torrented movies and series using a local Ollama model"
  homepage "https://github.com/barnaby/media-sorter"
  url "https://github.com/barnaby/media-sorter/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
  license "MIT"

  depends_on "python@3.12"

  def install
    # Create virtual environment and install package
    python = Formula["python@3.12"].opt_bin/"python3.12"
    venv = libexec/"venv"
    system python, "-m", "venv", venv

    # Upgrade pip and install the package
    system venv/"bin/pip", "install", "--upgrade", "pip"
    system venv/"bin/pip", "install", "."

    # Link the CLI tool to bin
    bin.install_symlink venv/"bin/media-sorter"
  end

  test do
    assert_match "usage: media-sorter", shell_output("#{bin}/media-sorter --help")
  end
end
