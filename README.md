# aparta

> Isole suas contas de desenvolvimento (git, GitHub CLI, gcloud) por pasta de projeto — e faça seus agentes de IA de terminal usarem a conta certa, sempre.

![CI](https://img.shields.io/badge/tests-passing-brightgreen) ![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue) ![License: MIT](https://img.shields.io/badge/license-MIT-yellow) ![PyPI](https://img.shields.io/badge/pypi-aparta-orange)

<!-- TODO: gravar demo com asciinema e substituir o placeholder abaixo -->
![demo placeholder](https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/demo.gif)

## Quick Start (English)

Working with multiple identities (personal + work, or several clients) means commits going out with the wrong e-mail, `gh`/`gcloud` having a single *global* active account, and AI coding agents inheriting whatever identity your shell happens to have. **aparta** automates the known manual fix — `includeIf` blocks in `~/.gitconfig`, parallel `gh` config dirs selected via `GH_CONFIG_DIR`, named `gcloud` configurations selected via `CLOUDSDK_ACTIVE_CONFIG_NAME` — and injects those env vars per project into your terminal AI agents.

```bash
uvx aparta        # first run drops you straight into the interactive wizard
# not on PyPI yet? run straight from GitHub:
uvx --from git+https://github.com/lucascarvalhal/aparta aparta
```

Pick your AI agents, describe each context (folder, git e-mail, SSH key, gh/gcloud accounts — aparta lists what is already logged in), review the summary, confirm once. Done. `aparta doctor` verifies everything afterwards.

Requirements: Python >= 3.10; `gh` and `gcloud` must already be authenticated (aparta selects credentials, it never logs in for you). Nothing ever leaves your machine.

---

## O problema

Quem trabalha com mais de uma identidade vive esbarrando no mesmo atrito:

- commits saindo com o **e-mail errado** dependendo da pasta;
- `gh` e `gcloud` têm **uma conta ativa global** — trocar num terminal troca em todos;
- agentes de IA de terminal herdam o ambiente do shell e usam a conta errada.

O **aparta** automatiza a solução manual conhecida: blocos `[includeIf "gitdir:..."]` no `~/.gitconfig`, diretórios de config paralelos do `gh` (`GH_CONFIG_DIR`), configurations nomeadas do `gcloud` (`CLOUDSDK_ACTIVE_CONFIG_NAME`) — e injeta essas variáveis por projeto nos seus agentes de IA.

## Instalação

```bash
uvx aparta          # roda sem instalar (recomendado para começar)
pip install aparta  # ou instale de vez
```

> Enquanto o pacote não está no PyPI, use a instalação direto do GitHub:
>
> ```bash
> uvx --from git+https://github.com/lucascarvalhal/aparta aparta
> ```

Rodar `aparta` sem argumentos na primeira vez abre o **wizard interativo**; com perfis já configurados, abre um menu (novo perfil / apply / doctor / list).

## Agentes suportados

| Agente | Mecanismo de injeção |
|---|---|
| Claude Code | campo `env` em `.claude/settings.local.json` (merge) |
| Codex CLI | seção `[env]` em `.codex/config.toml` do repositório |
| Gemini CLI | `.gemini/.env` do projeto (carregado nativamente pelo CLI) |
| Antigravity | `terminal.integrated.env.{osx,linux}` em `.vscode/settings.json` |
| direnv (genérico) | linhas `export` no `.envrc` — funciona para qualquer ferramenta |

Adicionar suporte a um agente novo = criar um arquivo em `src/aparta/agents/` (registro automático).

## O que cada perfil configura

| Ferramenta | Mecanismo |
|---|---|
| git | `~/.gitconfig-<perfil>` com `user.email`, `core.sshCommand` (chave SSH própria) e opcionalmente `url insteadOf`; incluído via `[includeIf "gitdir:~/pasta/"]` |
| gh | cópia de `~/.config/gh` para `~/.config/gh-<perfil>` + `gh auth switch` na cópia; seleção via `GH_CONFIG_DIR` (tokens ficam no keyring — sem novo login) |
| gcloud | `gcloud config configurations create <perfil> --no-activate`; seleção via `CLOUDSDK_ACTIVE_CONFIG_NAME` |
| agentes | as duas env vars acima injetadas por repositório, pelos adapters da tabela anterior |

## Comandos

```bash
aparta            # wizard (1ª vez) ou menu
aparta init       # wizard: agentes → contextos → resumo → confirmação → apply
aparta apply <p>  # aplica um perfil
aparta doctor     # valida tudo (tabela: git email por repo, gh auth, gcloud, env)
aparta list       # perfis configurados
aparta --dry-run apply <p>   # mostra o diff completo sem tocar em nada
```

## Segurança

- **Backups sempre**: toda escrita em arquivo existente cria antes `<arquivo>.bak-aparta-<timestamp>`.
- **Merge, nunca substituição**: no `~/.gitconfig` blocos são adicionados apenas se ausentes; nos configs dos agentes só o objeto de env é mesclado — o resto é preservado.
- **`--dry-run` global**: veja o diff exato antes de aplicar qualquer coisa.
- **Nada sai da sua máquina**: o aparta não faz chamadas de rede; ele apenas organiza arquivos locais e credenciais que **você já criou** com `gh auth login` e `gcloud auth login` (faça login antes de usar o aparta).

Estado em `~/.config/aparta/profiles.toml` (override com `APARTA_CONFIG_DIR`).

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Resumo: `uv sync`, `uv run pytest`, um adapter novo é um arquivo em `src/aparta/agents/` com `name`, `display_name` e os métodos `detect/inject/validate`.

## Licença

[MIT](LICENSE)
