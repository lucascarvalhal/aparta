# VHS script for the README demo (vhs docs/demo.tape).
# Run docs/demo-setup.sh first to build the fake home in /tmp/aparta-demo-home.

Output docs/demo.gif

Set FontSize 15
Set Width 1100
Set Height 640
Set Theme "Catppuccin Mocha"
Set TypingSpeed 60ms

Env HOME "/tmp/aparta-demo-home"
Env XDG_CONFIG_HOME "/tmp/aparta-demo-home/.config"
Env APARTA_CONFIG_DIR "/tmp/aparta-demo-home/.config/aparta"
Env CLOUDSDK_CONFIG "/tmp/aparta-demo-home/.config/gcloud"
Env PATH "/tmp/aparta-demo-home/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

Hide
Type "clear" Enter
Show

Type "aparta"
Sleep 800ms
Enter
Sleep 2.5s

# agents: keep Claude Code selected
Enter
Sleep 1.5s

# start mode: detect what I already use
Enter
Sleep 3s

# extra folder outside home: none
Enter
Sleep 1.5s

# suggestions checkbox: both groups pre-selected
Enter
Sleep 2s

# ---- profile 1/2: acme (everything pre-filled) ----
Enter
Sleep 900ms
Enter
Sleep 900ms
Enter
Sleep 1.2s
# ssh key: first one (id_ed25519_acme)
Enter
Sleep 1.2s
# remotes alias: none
Enter
Sleep 1.2s
# gh account: ana-acme
Enter
Sleep 1.2s
# gcloud: skip
Down
Enter
Sleep 1.5s

# ---- profile 2/2: personal ----
Enter
Sleep 900ms
Enter
Sleep 900ms
Enter
Sleep 1.2s
# ssh key: second one (id_ed25519_personal)
Down
Enter
Sleep 1.2s
Enter
Sleep 1.2s
# gh account: anadev
Down
Enter
Sleep 1.2s
# gcloud: skip
Down
Enter
Sleep 1.5s

# another profile? no
Enter
Sleep 2.5s

# summary shown; apply now
Enter
Sleep 4s

Type "aparta doctor"
Sleep 500ms
Enter
Sleep 5s
