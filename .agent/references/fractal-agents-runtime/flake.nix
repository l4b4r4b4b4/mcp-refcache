{
  description = "Fractal Agents Runtime — Polyglot monorepo for LangGraph-compatible agent runtimes (Python/Robyn + TypeScript/Bun)";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
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
          name = "fractal-dev";

          targetPkgs = pkgs':
            with pkgs'; [
              # ── Monorepo Workspace ──────────────────────────────────
              bun # Bun runtime + workspace orchestration + TS app

              # ── Python App (apps/python) ────────────────────────────
              python312 # Python 3.12 for Robyn runtime
              uv # Fast Python package manager (replaces pip)
              ruff # Python linter + formatter

              # ── System Libraries ────────────────────────────────────
              # Required for building Python wheels with native extensions
              zlib
              stdenv.cc.cc.lib
              openssl # SSL/TLS for aiohttp, supabase, etc.

              # ── Container & Kubernetes ──────────────────────────────
              docker
              docker-compose
              kubectl # Kubernetes CLI
              kubernetes-helm # Helm chart development + deployment
              k9s # Terminal UI for Kubernetes debugging
              minikube # Local Kubernetes cluster for testing
              kubectx # Kubernetes context/namespace switcher
              stern # Multi-pod log tailing

              # ── HTTP & API Testing ──────────────────────────────────
              httpie # Human-friendly HTTP client
              hurl # HTTP testing with plain text
              curlie # curl + httpie ease of use

              # ── Development Utilities ───────────────────────────────
              watchexec # File watcher for auto-reload
              jq # JSON processor
              tree # Directory tree viewer
              lefthook # Git hooks manager (polyglot, fast)

              # ── Version Control ─────────────────────────────────────
              git
              git-lfs
              curl
              wget

              # ── Shells ──────────────────────────────────────────────
              zsh
              bash
            ];

          profile = ''
            echo ""
            echo "🧬 Fractal Agents Runtime — Development Environment"
            echo "═══════════════════════════════════════════════════"
            echo ""

            # ── Core Tooling Versions ──
            echo "📦 Bun:        $(bun --version)"
            echo "🐍 Python:     $(python3 --version 2>&1 | cut -d' ' -f2)"
            echo "📎 uv:         $(uv --version 2>&1 | cut -d' ' -f2)"
            echo "🔍 Ruff:       $(ruff --version 2>&1 | cut -d' ' -f2)"
            echo ""

            # ── Bun version consistency check ──
            BUN_VERSION=$(bun --version)
            export BUN_VERSION
            bun run check:bun-version 2>/dev/null || true

            # ── Auto-sync @types/bun with Bun runtime version ──

            if [ -f "package.json" ] && grep -q "@types/bun" package.json; then
              CURRENT_TYPES=$(bun pm ls @types/bun 2>/dev/null | grep -oP '@types/bun@\K[^"]+' | head -1 || echo "")
              if [ -n "''${CURRENT_TYPES}" ] && [ "''${CURRENT_TYPES}" != "''${BUN_VERSION}" ]; then
                echo "🔧 Syncing @types/bun: ''${CURRENT_TYPES} → ''${BUN_VERSION}"
                bun add -d "@types/bun@''${BUN_VERSION}" > /dev/null 2>&1 && echo "✅ @types/bun updated" || echo "⚠️  Run 'bun add -d @types/bun@''${BUN_VERSION}' manually"
              fi
            fi

            # ── Python App Setup (apps/python) ──
            if [ -d "apps/python" ]; then
              if [ ! -d "apps/python/.venv" ]; then
                echo "🐍 Creating Python virtual environment in apps/python..."
                (cd apps/python && uv venv --python python3.12 --prompt "fractal-python")
              fi

              if [ -d "apps/python/.venv" ]; then
                unset VIRTUAL_ENV
                source apps/python/.venv/bin/activate
                export PYTHONPATH="$PWD/apps/python/src:''${PYTHONPATH:-}"
                echo "✅ Python venv: activated (apps/python/.venv)"
              fi

              # Auto-sync Python deps if lockfile exists
              if [ -f "apps/python/uv.lock" ] && [ -d "apps/python/.venv" ]; then
                (cd apps/python && uv sync --quiet 2>/dev/null) && echo "✅ Python deps: synced" || echo "⚠️  Run 'cd apps/python && uv sync' manually"
              fi
            else
              echo "ℹ️  apps/python/ not found — create it to enable the Python runtime"
            fi

            # ── Bun Workspace Setup ──
            if [ -f "package.json" ]; then
              if [ ! -d "node_modules" ]; then
                echo "📦 Installing bun workspace dependencies..."
                bun install --silent 2>/dev/null && echo "✅ Bun workspace: installed" || echo "⚠️  Run 'bun install' manually"
              else
                echo "✅ Bun workspace: ready"
              fi
            fi

            # ── npm Registry Auth ──
            NPM_USER=$(npm whoami 2>/dev/null || echo "")
            if [ -n "''${NPM_USER}" ]; then
              echo "✅ npm: logged in as ''${NPM_USER}"
            else
              echo "ℹ️  npm: not logged in (required for publishing)"
              printf "   Log in now? (y/N) "
              read -r NPM_LOGIN
              if [ "''${NPM_LOGIN}" = "y" ] || [ "''${NPM_LOGIN}" = "Y" ]; then
                npm login && echo "✅ npm: logged in as $(npm whoami 2>/dev/null)" || echo "⚠️  npm login failed — run 'npm login' manually"
              fi
            fi

            echo ""

            # ── Prevent wrong package managers ──
            alias pip='echo "❌ Use uv instead of pip! Run: uv add <package>" && false'
            alias pip3='echo "❌ Use uv instead of pip3! Run: uv add <package>" && false'
            alias pip-compile='echo "❌ Use uv instead of pip-compile! Run: uv lock" && false'
            npm() {
              case "$1" in
                login|whoami|logout|token) command npm "$@" ;;
                *) echo "❌ Use bun instead of npm! Run: bun install <package>" && return 1 ;;
              esac
            }
            alias yarn='echo "❌ Use bun instead of yarn! Run: bun install" && false'
            alias pnpm='echo "❌ Use bun instead of pnpm! Run: bun install" && false'

            echo "📚 Common Commands:"
            echo ""
            echo "  Monorepo (root):"
            echo "    bun install                  - Install all workspace deps"
            echo "    bun run test                 - Run all tests"
            echo "    bun run lint                 - Lint all apps"
            echo "    bun run format:python        - Format Python code"
            echo ""
            echo "  Python Runtime (apps/python):"
            echo "    bun run dev:python           - Start Robyn server"
            echo "    bun run test:python          - Run Python tests"
            echo "    bun run lint:python          - Lint Python code"
            echo "    cd apps/python && uv add <pkg>  - Add Python dependency"
            echo "    cd apps/python && uv sync    - Sync Python deps"
            echo ""
            echo "  TypeScript Runtime (apps/ts):"
            echo "    bun run dev:ts               - Start TS dev server"
            echo "    bun run test:ts              - Run TS tests"
            echo ""
            echo "  Docker & Kubernetes:"
            echo "    bun run docker:python        - Build Python Docker image"
            echo "    helm template apps/python/helm  - Render Helm chart locally"
            echo "    helm install fractal apps/python/helm  - Deploy to cluster"
            echo "    k9s                          - Launch Kubernetes TUI"
            echo "    stern fractal                - Tail logs from runtime pods"
            echo ""
            echo "  API Testing:"
            echo "    httpie POST :8081/health      - Test Robyn health endpoint"
            echo "    hurl --test tests/api.hurl    - Run HTTP test suite"
            echo ""
            echo "Ready to code! 🧬"
            echo ""
          '';

          runScript = "${pkgs.zsh}/bin/zsh";
        };
      in {
        devShells.default = pkgs.mkShell {
          shellHook = ''
            exec ${fhsEnv}/bin/fractal-dev
          '';
        };
      }
    );
}
