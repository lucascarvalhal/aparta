<p align="center">
  <img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/logo.svg" alt="aparta" width="480">
</p>

<p align="center">
  <a href="https://pypi.org/project/aparta/"><img src="https://img.shields.io/pypi/v/aparta" alt="PyPI"></a>
  <img src="https://img.shields.io/pypi/pyversions/aparta" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="Licença: MIT">
  <a href="https://github.com/lucascarvalhal/aparta/actions/workflows/ci.yml"><img src="https://github.com/lucascarvalhal/aparta/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <b>Português (Brasil)</b>
</p>

O **aparta** isola suas contas de desenvolvimento, git, GitHub CLI, gcloud, chaves SSH, por pasta de projeto, e faz seus agentes de IA de terminal (Claude Code, Codex, Gemini CLI, Antigravity) usarem a identidade certa, sempre.

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/demo.gif" alt="aparta demo" width="900">

## Por que o aparta existe?

Quem trabalha com mais de uma identidade, emprego, freela, clientes, open source, conhece o roteiro:

- Você commita no repositório de um cliente e só depois percebe que o commit saiu **com o seu e-mail pessoal** (ou pior: seu projeto pessoal saiu com o e-mail da empresa). Reescrever histórico publicado é doloroso; às vezes, impossível.
- `gh` e `gcloud` têm **uma conta ativa global**. Trocar num terminal troca em *todos*, inclusive naquele outro onde um script de deploy estava prestes a rodar contra o projeto errado.
- Agentes de IA de terminal herdam a identidade que o shell tiver na hora. Um agente que clona, commita, faz push e chama APIs de nuvem por você multiplica a chance de acidente.

A solução é conhecida por quem já se queimou: blocos `[includeIf "gitdir:..."]` no `~/.gitconfig`, diretórios paralelos de config do `gh` (`GH_CONFIG_DIR`), configurações nomeadas do `gcloud` (`CLOUDSDK_ACTIVE_CONFIG_NAME`), apelidos de host no SSH. Funciona muito bem, mas é chato de montar na mão, fácil de errar num detalhe, e ninguém documenta como fazer os agentes de IA respeitarem tudo isso.

**O aparta automatiza o processo inteiro.** A pasta decide a identidade. Entrou em `~/work/acme`, o git, o gh, o gcloud e os agentes são o "você da acme". Entrou em `~/pessoal`, são você mesmo. Sem trocar nada, sem lembrar de nada, sem acidente.

## Como funciona

Um comando, um wizard interativo:

- **Detecta o que você já usa**, contas gh/gcloud logadas, chaves SSH e atalhos de host, blocos `includeIf` existentes e todos os repositórios git do disco, agrupados por pasta e e-mail de commit. Configurações existentes viram sugestões pré-preenchidas: confirmar um perfil é apertar Enter.
- **Ou começa do zero**, conecte uma conta nova do GitHub (`gh auth login` isolado no config dir do perfil), uma conta Google nova, gere uma chave SSH (e envie para o GitHub na hora).
- **Aplica com segurança**, todo arquivo tocado ganha backup (`.bak-aparta-<timestamp>`) e recebe merge, nunca é substituído. `--dry-run` mostra o diff completo sem alterar nada. Nada sai da sua máquina.
- **Verifica**, `aparta doctor` confere o estado real: e-mail resolvido em cada repo, auth do gh, config do gcloud, env injetado nos agentes.

### Telas

*O wizard detecta sua configuração e pré-preenche tudo:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/wizard.svg" alt="wizard do aparta" width="820">

*Um resumo, uma confirmação, com rede de proteção:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/resumo.svg" alt="resumo do aparta" width="820">

*`aparta scan` mostra o que foi encontrado sem tocar em nada:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/scan.svg" alt="aparta scan" width="820">

*`aparta doctor` prova que cada perfil está funcionando:*

<img src="https://raw.githubusercontent.com/lucascarvalhal/aparta/main/docs/doctor.svg" alt="aparta doctor" width="680">

## Instalação

Requer Python ≥ 3.10. `gh` e `gcloud` são opcionais, o aparta seleciona credenciais das ferramentas que você usa; ele nunca faz login sozinho (a menos que você peça, no wizard).

**Recomendado:** instale como ferramenta permanente com o [uv](https://docs.astral.sh/uv/), é rápido, isolado dos seus projetos e trivial de atualizar:

```bash
uv tool install aparta     # recomendado
aparta                     # daqui em diante é só isso
```

Outros caminhos, conforme o seu setup:

```bash
uvx aparta            # experimentar sem instalar nada
pipx install aparta   # mesma ideia do uv tool, usando pipx
pip install aparta    # pip puro, vai para o ambiente ativo
npx aparta-cli        # lançador do ecossistema Node (requer uv ou pipx instalado)
```

Para atualizar depois: `uv tool upgrade aparta` (ou o equivalente da ferramenta escolhida).

## Idiomas

O CLI fala inglês e português do Brasil. A primeira execução do wizard pergunta qual você prefere e lembra da escolha; `APARTA_LANG=pt` ou `APARTA_LANG=en` sobrepõe a escolha salva, e sem nada disso o locale (`LANG`) decide.

## Começando

```bash
aparta            # primeira execução abre o wizard; depois, um menu
```

1. Escolha quais agentes de IA devem receber o ambiente por projeto (Claude Code, Codex, Gemini CLI, Antigravity, ou um `.envrc` genérico via direnv).
2. Escolha **"Detectar o que já uso"** (recomendado) ou **"Começar do zero"**.
3. Confirme cada perfil sugerido, nome, pasta, e-mail do git, chave SSH, atalho de remote, conta gh, conta/projeto gcloud vêm pré-preenchidos da varredura.
4. Opcionalmente adote repositórios soltos que vivem fora das pastas dos perfis (eles ficam onde estão; a identidade é aplicada localmente via `include.path` do git).
5. Revise o resumo, confirme uma vez. Pronto.

```bash
aparta doctor     # verifica se tudo resolve para a identidade certa
aparta scan       # somente leitura: mostra os grupos de projetos detectados
aparta apply X    # reaplica um perfil (ex.: depois de clonar repos novos)
aparta list       # lista os perfis configurados
aparta --dry-run  # qualquer comando: mostra diffs, não altera nada
```

## O que cada perfil configura

| Ferramenta | Mecanismo |
|---|---|
| git | `~/.gitconfig-<perfil>` com `user.email`, `core.sshCommand` (chave própria) e opcionalmente `url insteadOf`; incluído via `[includeIf "gitdir:~/pasta/"]` |
| GitHub CLI | cópia de `~/.config/gh` para `~/.config/gh-<perfil>` + `gh auth switch` na cópia; seleção via `GH_CONFIG_DIR` (tokens ficam no keyring, sem novo login) |
| gcloud | configuração nomeada (`--no-activate`) com conta/projeto; seleção via `CLOUDSDK_ACTIVE_CONFIG_NAME` |
| SSH | chave por perfil; opcionalmente reescrita de remotes via atalho do `~/.ssh/config` |
| Repos soltos | `include.path` local no `.git/config` apontando para o gitconfig do perfil, identidade completa sem mover a pasta |

## Agentes de IA suportados

| Agente | Mecanismo de injeção |
|---|---|
| Claude Code | campo `env` em `.claude/settings.local.json` (merge) |
| Codex CLI | seção `[env]` em `.codex/config.toml` do repositório |
| Gemini CLI | `.gemini/.env` do projeto (carregado nativamente pelo CLI) |
| Antigravity | `terminal.integrated.env.{osx,linux}` em `.vscode/settings.json` |
| opencode | plugin `shell.env` gerado em `.opencode/plugins/aparta-env.js` |
| Cursor CLI | sem env nativo por projeto, herda o shell, coberto pelo adapter direnv |
| direnv (genérico) | linhas `export` no `.envrc`, funciona para qualquer ferramenta |

Adicionar suporte a um agente novo = criar um arquivo em `src/aparta/agents/` (registro automático).

## Modelo de segurança

- Toda escrita em arquivo existente cria backup com timestamp e faz **merge**: o aparta nunca sobrescreve seus dotfiles.
- `--dry-run` mostra cada mudança como diff antes de qualquer coisa.
- A varredura é 100% somente leitura.
- Nada é enviado para lugar nenhum. Sem telemetria, sem chamadas de rede além das que *você* dispara (`gh auth login`, `gcloud auth login`).

## Roadmap

- Mais agentes conforme ganharem suporte a config por projeto
- Suporte nativo a Windows (WSL já funciona)

## Contribuindo

Issues e PRs são bem-vindos, veja o [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md).

## Licença

[MIT](LICENSE)
