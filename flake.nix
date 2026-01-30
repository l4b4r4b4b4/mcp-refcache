{
  description = "mcp-refcache - Reference-based caching for FastMCP servers (Python + TypeScript monorepo)";

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
              # JavaScript/TypeScript (Bun)
              bun
              nodejs_22

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
            echo "📦 mcp-refcache Development Environment (Monorepo)"
            echo "==================================================="

            # Monorepo structure: packages/python/ and packages/typescript/
            PYTHON_PKG="$PWD/packages/python"

            # Create and activate uv virtual environment if it doesn't exist
            if [ -d "$PYTHON_PKG" ]; then
              if [ ! -d "$PYTHON_PKG/.venv" ]; then
                echo "📦 Creating Python virtual environment..."
                cd "$PYTHON_PKG" && uv venv --python python3.12 --prompt "mcp-refcache-py" && cd "$PWD"
              fi

              # Activate the virtual environment
              source "$PYTHON_PKG/.venv/bin/activate"

              # Set a recognizable name for IDEs
              export VIRTUAL_ENV_PROMPT="mcp-refcache-py"

              # Sync Python dependencies
              echo "🔄 Syncing Python dependencies..."
              cd "$PYTHON_PKG" && uv sync --quiet && cd "$OLDPWD"
            fi

            # Install Bun dependencies if package.json exists at root
            if [ -f "package.json" ]; then
              echo "🔄 Installing Bun dependencies..."
              bun install --silent 2>/dev/null || true
            fi

            echo ""
            echo "✅ Python: $(python --version 2>/dev/null || echo 'not activated')"
            echo "✅ uv:     $(uv --version)"
            echo "✅ Bun:    $(bun --version)"
            echo "✅ Node:   $(node --version)"
            echo "✅ PYTHONPATH: $PYTHON_PKG/src"
          '';

          runScript = ''
            # Set shell for the environment
            SHELL=${pkgs.zsh}/bin/zsh

            # Set PYTHONPATH to monorepo Python package
            export PYTHONPATH="$PWD/packages/python/src:$PWD"
            export SSL_CERT_FILE="/etc/ssl/certs/ca-bundle.crt"

            echo ""
            echo "📚 mcp-refcache Monorepo Quick Reference:"
            echo ""
            echo "🐍 Python (packages/python/):"
            echo "  cd packages/python && uv run pytest   - Run Python tests"
            echo "  cd packages/python && uv run ruff check . - Lint Python"
            echo "  bun run test:py                       - Run from root"
            echo ""
            echo "🟦 TypeScript (packages/typescript/):"
            echo "  cd packages/typescript && bun test    - Run TS tests"
            echo "  cd packages/typescript && bun run build - Build TS"
            echo "  bun run test:ts                       - Run from root"
            echo ""
            echo "📦 Monorepo Scripts (from root):"
            echo "  bun run test                          - Run all tests"
            echo "  bun run lint                          - Lint all code"
            echo "  bun install                           - Install TS deps"
            echo ""
            echo "🔧 Package Management:"
            echo "  cd packages/python && uv add <pkg>    - Add Python dep"
            echo "  cd packages/typescript && bun add <pkg> - Add TS dep"
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
