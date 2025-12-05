{
  description = "mcp-refcache - Reference-based caching for FastMCP servers";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };

        fhsEnv = pkgs.buildFHSEnv {
          name = "mcp-refcache-dev";

          targetPkgs = pkgs':
            with pkgs'; [
              # Python and uv
              python312
              uv
              just

              # OpenAPI Tools
              openapi-generator-cli
              swagger-cli
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
              gibo # Generate .gitignore templates
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
            # Set SSL certificate path for HTTPS requests
            export SSL_CERT_FILE="/etc/ssl/certs/ca-bundle.crt"

            # Set PYTHONPATH to project root
            export PYTHONPATH="$PWD/src:$PWD"

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
              echo "🔄 Syncing dependencies from pyproject.toml..."
              uv sync --quiet
            else
              echo "⚠️  No pyproject.toml found. Run 'uv init' to create project."
            fi

            echo ""
            echo "✅ Python: $(python --version)"
            echo "✅ uv:     $(uv --version)"
            echo "✅ Virtual environment: activated (.venv)"
            echo "✅ PYTHONPATH: $PYTHONPATH"
          '';

          runScript = "${pkgs.zsh}/bin/zsh";
        };
      in {
        devShells.default = pkgs.mkShell {
          shellHook = ''
            exec ${fhsEnv}/bin/mcp-refcache-dev
          '';
        };

        packages.default = pkgs.python312;
      }
    );
}
