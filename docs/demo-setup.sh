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

# stub gh with two demo accounts so the wizard shows account selection
mkdir -p "$DEMO/.config/gh"
printf 'git_protocol: ssh\n' > "$DEMO/.config/gh/config.yml"
printf 'github.com:\n    user: ana-acme\n' > "$DEMO/.config/gh/hosts.yml"
cat > "$DEMO/bin/gh" << 'FAKE'
#!/bin/bash
if [ "$1 $2" = "auth status" ]; then
  cat << 'EOF'
github.com
  ✓ Logged in to github.com account ana-acme (keyring)
  ✓ Logged in to github.com account anadev (keyring)
EOF
fi
exit 0
FAKE
chmod +x "$DEMO/bin/gh"
cat > "$DEMO/bin/gcloud" << 'FAKE'
#!/bin/bash
exit 1
FAKE
chmod +x "$DEMO/bin/gcloud"

echo "demo home ready at $DEMO"
