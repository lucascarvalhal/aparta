<p align="right"><a href="CHANGELOG.md">English</a> | <b>Português (Brasil)</b></p>

# Changelog

Todas as mudanças relevantes do aparta estão documentadas aqui. O formato
segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.4.4] - 2026-08-19

### Segurança

- Os sdists da 0.4.1 à 0.4.3 incluíram por acidente arquivos locais de
  desenvolvimento e foram removidos do PyPI (os wheels nunca foram
  afetados). Os sdists agora são montados a partir de uma allowlist
  explícita, então arquivos perdidos não embarcam mais.

### Alterado

- As plataformas suportadas ficam explícitas: macOS, Linux e Windows via
  WSL. O suporte nativo a Windows sai do roadmap.
- O README recomenda o Orca e o Universal Memory como ferramentas
  companheiras.

## [0.4.3] - 2026-08-19

### Alterado

- As plataformas suportadas ficam explícitas: macOS, Linux e Windows via
  WSL. O suporte nativo a Windows sai do roadmap.

## [0.4.2] - 2026-08-19

### Alterado

- A documentação em português do Brasil foi reescrita como texto nativo, com
  uma voz mais amigável, em vez de tradução literal (README, CONTRIBUTING,
  SECURITY).
- As mensagens de conversa do CLI em português passaram pela mesma revisão de
  voz natural.

## [0.4.1] - 2026-08-19

### Adicionado

- `aparta remove <perfil>`: apaga um perfil e desfaz tudo que ele aplicou
  (env dos agentes, includes dos repos adotados, gitconfig e includeIf,
  config dir do gh, configuração do gcloud), com backups e `--dry-run`.
- `aparta help`: visão geral localizada de todos os comandos.
- Pergunta de idioma na primeira execução do wizard (inglês ou português),
  persistida; `APARTA_LANG` continua sobrepondo.
- Confirmações sim/não localizadas (`y/N` em inglês, `s/N` em português).
- Autocompletar de shell documentado (`aparta --install-completion`).
- Screenshots e demo agora existem nos dois idiomas, gerados a partir do
  catálogo real de mensagens.

### Alterado

- Documentação em inglês como padrão no repo, com gêmeos em português do
  Brasil (README, CONTRIBUTING, SECURITY, este changelog).
- O guia de instalação agora recomenda `uv tool install aparta`.

## [0.4.0] - 2026-08-19

### Adicionado

- Internacionalização completa: strings canônicas em inglês com catálogo
  completo em português do Brasil, escolhido por `APARTA_LANG` ou locale.
- Adapter do opencode via plugin `shell.env` gerado.
- Varredura da home inteira sem suposições de nome de pasta; o wizard varre
  pastas extras e o `aparta scan` aceita caminhos explícitos.
- `Profile.git_host` parametriza a reescrita de remotes (GitLab, Bitbucket
  e hosts self-hosted funcionam).
- Pacote lançador npm `aparta-cli`, então `npx aparta-cli` roda o CLI.
- Automação de release: workflow por tag publicando no PyPI e npm via
  trusted publishing, com environments protegidos e checagem de versões.

### Alterado

- Nova camada de aplicação (`apply.py`) com registry de backends; adapters
  expõem `read_env` e a descoberta lê configurações anteriores pelo
  registry.
- Caminhos respeitam `XDG_CONFIG_HOME` e `CLOUDSDK_CONFIG`.

### Corrigido

- Um repo com config JSON/TOML quebrada não aborta mais o apply nem o
  doctor.
- O `gh auth switch` rodava com ambiente reduzido que podia quebrar o
  acesso ao keyring.
- Detecção de configurações gcloud existentes independente de idioma.

## [0.3.0] - 2026-08-18

### Adicionado

- Modos de início no wizard: detectar a configuração existente ou começar
  do zero.
- Fluxos de conexão: contas novas do GitHub/Google logadas direto na config
  isolada do perfil, geração de chave SSH com envio via `gh ssh-key add`.
- Adoção de repos soltos: repos fora das raízes ganham a identidade do
  perfil por um include local do git, sem mover pastas.
- Descoberta pré-preenche chaves SSH, atalhos de host, usuários gh, contas
  gcloud e projetos GCP da configuração existente.
- Atalhos de host do `~/.ssh/config` oferecidos como select para reescrita
  de remotes.

## [0.2.0] - 2026-08-18

### Adicionado

- Descoberta no disco: blocos `includeIf` existentes e repositórios
  agrupados por pasta e e-mail viram sugestões pré-preenchidas no wizard.
- Comando somente leitura `aparta scan`.
- Cabeçalho por grupo e terminologia unificada no wizard.

## [0.1.0] - 2026-08-18

### Adicionado

- Primeira versão: wizard `init`, `apply`, `doctor`, `list`, `--dry-run`
  global.
- Backends: git (`includeIf` e gitconfig por perfil), GitHub CLI (config
  dir paralelo via `GH_CONFIG_DIR`), gcloud (configurações nomeadas).
- Adapters de agentes: Claude Code, Codex CLI, Gemini CLI, Antigravity,
  direnv.
- SafeWriter: backups com timestamp, merges, diffs em dry-run.

[Não lançado]: https://github.com/lucascarvalhal/aparta/compare/v0.4.4...HEAD
[0.4.4]: https://github.com/lucascarvalhal/aparta/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/lucascarvalhal/aparta/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/lucascarvalhal/aparta/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/lucascarvalhal/aparta/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/lucascarvalhal/aparta/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/lucascarvalhal/aparta/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/lucascarvalhal/aparta/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lucascarvalhal/aparta/releases/tag/v0.1.0
