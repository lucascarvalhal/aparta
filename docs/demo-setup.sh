#!/bin/bash
# Builds a fake home for the VHS demo: repos with demo identities, fake SSH
# keys, isolated config. Nothing from the real machine leaks in.
set -euo pipefail

DEMO=/tmp/aparta-demo-home
rm -rf "$DEMO"
mkdir -p "$DEMO"

make_repo() { # path email
  mkdir -p "$1"
  git init -q "$1"
  git -C "$1" config user.email "$2"
  git -C "$1" config user.name "Ana Dev"
}

make_repo "$DEMO/work/acme/api" "ana@acme.com"
make_repo "$DEMO/work/acme/billing" "ana@acme.com"
make_repo "$DEMO/work/acme/web" "ana@acme.com"
make_repo "$DEMO/personal/blog" "ana.dev@gmail.com"
make_repo "$DEMO/personal/dotfiles" "ana.dev@gmail.com"

mkdir -p -m 700 "$DEMO/.ssh"
printf 'fake key for demo\n' > "$DEMO/.ssh/id_ed25519_acme"
printf 'ssh-ed25519 AAAA fake\n' > "$DEMO/.ssh/id_ed25519_acme.pub"
printf 'fake key for demo\n' > "$DEMO/.ssh/id_ed25519_personal"
printf 'ssh-ed25519 AAAA fake\n' > "$DEMO/.ssh/id_ed25519_personal.pub"

mkdir -p "$DEMO/bin"
cat > "$DEMO/bin/aparta" << 'WRAP'
#!/bin/bash
exec uv run --project /Users/lucascarvalhal/pessoal/aparta aparta "$@"
WRAP
chmod +x "$DEMO/bin/aparta"

echo "demo home ready at $DEMO"
