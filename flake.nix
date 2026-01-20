{
  description = "mcp-refcache - Reference-based caching for FastMCP servers";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # Pinned nixpkgs for packages broken in unstable
    nixpkgs-pinned = {
      url = "github:NixOS/nixpkgs/418468ac9527e799809c900eda37cbff999199b6";
    };
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    nixpkgs-pinned,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
        # Pinned packages for those broken in unstable
        pkgs-pinned = import nixpkgs-pinned {
          inherit system;
        };

        fhsEnv = pkgs.buildFHSEnv {
          name = "mcp-refcache-dev-env";

          targetPkgs = pkgs':
            with pkgs'; [
              # Python and uv
              python312
              uv
              just
              cookiecutter
              # OpenAPI Tools
              openapi-generator-cli
              pkgs-pinned.swagger-cli # pinned: broken in nixpkgs unstable (2026-01-05)
              yq

              # System libraries (required for some dependencies)
              zlib
              stdenv.cc.cc.lib

              # Shells
              zsh
              bash

              # Linting & Formatting
              ruff
              pre-commit

              # Development tools
              git
              git-lfs
              gibo
              curl
              wget
              unzip
              jq
              tree
              httpie

              # Documentation
              pandoc
            ];

          profile = ''
            echo "📦 mcp-refcache Development Environment"
            echo "========================================"

            # Create and activate uv virtual environment if it doesn't exist
            if [ ! -d ".venv" ]; then
              echo "📦 Creating uv virtual environment..."
              uv venv --python python3.12 --prompt "mcp-refcache"
            fi

            # Activate the virtual environment
            source .venv/bin/activate

            # Set a recognizable name for IDEs
            export VIRTUAL_ENV_PROMPT="mcp-refcache"

            # Sync dependencies
            if [ -f "pyproject.toml" ]; then
              echo "🔄 Syncing dependencies..."
              uv sync --quiet
            else
              echo "⚠️  No pyproject.toml found. Run 'uv init' to create project."
            fi

            echo ""
            echo "✅ Python: $(python --version)"
            echo "✅ uv:     $(uv --version)"
            echo "✅ Virtual environment: activated (.venv)"
            echo "✅ PYTHONPATH: $PWD/src:$PWD"
          '';

          runScript = ''
            # Set shell for the environment
            SHELL=${pkgs.zsh}/bin/zsh

            # Set PYTHONPATH to project root for module imports
            export PYTHONPATH="$PWD/src:$PWD"
            export SSL_CERT_FILE="/etc/ssl/certs/ca-bundle.crt"

            echo ""
            echo "📚 mcp-refcache Quick Reference:"
            echo ""
            echo "🔧 Development:"
            echo "  uv sync                    - Sync dependencies"
            echo "  uv run pytest              - Run tests"
            echo "  uv run ruff check .        - Lint code"
            echo "  uv run ruff format .       - Format code"
            echo "  uv lock --upgrade          - Update all dependencies"
            echo ""
            echo "📦 Package Management:"
            echo "  uv add <package>           - Add runtime dependency"
            echo "  uv add --dev <package>     - Add dev dependency"
            echo "  uv remove <package>        - Remove dependency"
            echo ""
            echo "🔗 Git Ignore Templates:"
            echo "  gibo list                  - List available templates"
            echo "  gibo dump Python > .gitignore  - Generate Python .gitignore"
            echo ""
            echo "🧪 Testing in other projects:"
            echo "  uv add --editable ../mcp-refcache           - Local dev install"
            echo "  uv add mcp-refcache@git+https://github.com/l4b4r4b4b4/mcp-refcache"
            echo ""
            echo "🚀 Ready to build! 📦"
            echo ""

            # Start zsh shell
            exec ${pkgs.zsh}/bin/zsh
          '';
        };
      in {
        devShells.default = pkgs.mkShell {
          shellHook = ''
            exec ${fhsEnv}/bin/mcp-refcache-dev-env
          '';
        };

        packages.default = pkgs.python312;
      }
    );
}
