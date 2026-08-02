class Marquee < Formula
  include Language::Python::Virtualenv

  desc "Sort torrented movies and series using a local Ollama model"
  homepage "https://github.com/b-vanstraaten/marquee"
  url "https://github.com/b-vanstraaten/marquee/archive/refs/tags/v0.3.2.tar.gz"
  sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  license "MIT"

  depends_on "ollama"
  depends_on "python@3.12"

  # Every runtime dependency is pinned and vendored here so `brew install`
  # never needs to resolve anything from PyPI -- versions match uv.lock.
  # Order matters: each resource must come after everything it depends on,
  # since they're installed one at a time into the same venv.

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/0b/a7/71ac2cff56fec219ed242bb11b8efb69fcc4bec75db06fb7bfe35de520e6/certifi-2026.7.22-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "h11" do
    url "https://files.pythonhosted.org/packages/04/4b/29cac41a4d98d144bf5f6d33995617b185d14b22401f75ca86f384e87ff1/h11-0.16.0-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/1e/5e/d4e9f1a599fb8e573b7b87160658329fbf28d19eac2718f51fc3def3aa5a/idna-3.18-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/b3/38/89ba8ad64ae25be8de66a6d463314cf1eb366222074cfda9ee839c56a4b4/mdurl-0.1.2-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "typing-extensions" do
    url "https://files.pythonhosted.org/packages/49/d3/b8441a820a491ddfc024b0b0cf0393375b75ea13866d9c66727e54c2fc80/typing_extensions-4.16.0-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "annotated-types" do
    url "https://files.pythonhosted.org/packages/99/91/8acff4f5e50511b911bbccb72b8628a49c68ce14148cd9f6431094859a90/annotated_types-0.8.0-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/f4/7e/a72dd26f3b0f4f2bf1dd8923c85f7ceb43172af56d63c7383eb62b332364/pygments-2.20.0-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "anyio" do
    url "https://files.pythonhosted.org/packages/da/35/f2287558c17e29fafc8ef3daf819bb9834061cfa43bff8014f7df7f63bdc/anyio-4.14.2-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "httpcore" do
    url "https://files.pythonhosted.org/packages/7e/f5/f66802a942d491edb555dd61e3a9961140fd64c90bce1eafd741609d334d/httpcore-1.0.9-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/2a/39/e50c7c3a983047577ee07d2a9e53faf5a69493943ec3f6a384bdc792deb2/httpx-0.28.1-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "typing-inspection" do
    url "https://files.pythonhosted.org/packages/dc/9b/47798a6c91d8bdb567fe2698fe81e0c6b7cb7ef4d13da4114b41d239f65d/typing_inspection-0.4.2-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  # pydantic-core is a compiled (Rust) extension -- there's no pure-Python
  # wheel, so each platform needs its own pinned binary.
  resource "pydantic-core" do
    on_macos do
      on_arm do
        url "https://files.pythonhosted.org/packages/19/95/6195171e385007300f0f5574592e467c568becce2d937a0b6804f218bc49/pydantic_core-2.46.4-cp312-cp312-macosx_11_0_arm64.whl"
        sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
      end
      on_intel do
        url "https://files.pythonhosted.org/packages/ce/8c/af022f0af448d7747c5154288d46b5f2bc5f17366eaa0e23e9aa04d59f3b/pydantic_core-2.46.4-cp312-cp312-macosx_10_12_x86_64.whl"
        sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
      end
    end
    on_linux do
      url "https://files.pythonhosted.org/packages/5f/97/2aab507d3d00ca626e8e57c1eac6a79e4e5fbcc63eb99733ff55d1717f65/pydantic_core-2.46.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
      sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
    end
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/fd/7b/122376b1fd3c62c1ed9dc80c931ace4844b3c55407b6fb2d199377c9736f/pydantic-2.13.4-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/b3/81/4da04ced5a082363ecfa159c010d200ecbd959ae410c10c0264a38cac0f5/markdown_it_py-4.2.0-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/82/3b/64d4899d73f91ba49a8c18a8ff3f0ea8f1c1d75481760df8c68ef5235bf5/rich-15.0.0-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  resource "ollama" do
    url "https://files.pythonhosted.org/packages/c4/ab/d6722beeb2d10f7a3b9ff49375708904fde18f82b5609a0bc4aeb5996a4d/ollama-0.6.2-py3-none-any.whl"
    sha256 "1025440c507ebf3b10c73a96b46b3a48eb76b3ba9ffbe3466ffdcb6dd80a7375"
  end

  def install
    venv = virtualenv_create(libexec, "python3.12")

    # pydantic-core's wheel filename doesn't match the "*-py3-none-any.whl"
    # pattern virtualenv_install_with_resources uses to auto-detect a staged
    # wheel's path, so it's staged and installed explicitly here, before
    # anything that depends on it.
    resource("pydantic-core").stage do
      whl = Pathname.pwd.children.find { |f| f.extname == ".whl" }
      venv.pip_install whl
    end

    venv.pip_install resources.reject { |r| r.name == "pydantic-core" }
    venv.pip_install_and_link buildpath
  end

  def caveats
    <<~EOS
      marquee needs a running Ollama server with a model pulled:
        ollama serve &
        ollama pull llama3.2
      (marquee checks for both and tells you exactly what's missing if not.)
    EOS
  end

  test do
    assert_match "usage: marquee", shell_output("#{bin}/marquee --help")
  end
end
